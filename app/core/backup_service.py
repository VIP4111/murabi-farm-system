"""
النسخ الاحتياطي (بند 34 بالمواصفة الرئيسية) — نسخ محلي بسيط لملف قاعدة
البيانات، يشتغل فقط لما القاعدة SQLite (بيئة التطوير الحالية).

**تنبيه صادق**: لو انتقلت لإنتاج فعلي على PostgreSQL (خطة الترقية
الموثّقة بـROADMAP.md — تغيير `DATABASE_URL` بس)، هذا الزر ما يشتغل
إطلاقاً — نسخ احتياطي حقيقي لقاعدة إنتاج يحتاج أدوات مستوى قاعدة
البيانات (`pg_dump`، WAL archiving، لقطات مزوّد الاستضافة المُدارة)
خارج نطاق أي زر بالتطبيق نفسه. `is_backup_supported()` تكشف هذي الحالة
وتعرض تنبيهاً واضحاً بالواجهة بدل ما تعطي إحساس أمان زائف.

بند إضافي (2026-09-01) — حادثة حقيقية: قاعدة PostgreSQL المجانية على
Render انتهت صلاحيتها تلقائياً (سياسة 90 يوم) وانقطع الوصول لكل
البيانات، وما كان فيه أي نسخة احتياطية فعلية لأن الزر أعلاه معطَّل
عمداً على PostgreSQL. الحل الدائم: `export_all_tables_json()` — تصدير
عام يشتغل على أي قاعدة بيانات (SQLite محلياً أو PostgreSQL بالإنتاج)
بدون أي فرق، ويُرسَل مباشرة لجهاز المستخدم (تنزيل فوري، صفر تخزين
بالسيرفر) — عشان يقدر يحفظه بنفسه بأي وقت، بغض النظر عن نوع القاعدة
أو مصير حسابها لاحقاً."""
import io
import json
import os
import shutil
from datetime import date, datetime, timezone, time
from decimal import Decimal
from flask import current_app
from flask_babel import gettext as _
from app.extensions import db


def _sqlite_db_path() -> str | None:
    uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
    if not uri.startswith("sqlite:"):
        return None
    raw = uri.split("sqlite:", 1)[1]  # '///farm_system.db' أو '////abs/path.db'
    if raw.startswith("////"):
        return raw[3:]
    if raw.startswith("///"):
        return os.path.join(current_app.instance_path, raw[3:])
    return None


def is_backup_supported() -> bool:
    path = _sqlite_db_path()
    return bool(path and os.path.exists(path))


def _backup_dir() -> str:
    path = os.path.join(current_app.instance_path, "backups")
    os.makedirs(path, exist_ok=True)
    return path


def create_backup() -> str:
    db_path = _sqlite_db_path()
    if not db_path or not os.path.exists(db_path):
        raise RuntimeError(_(
            "النسخ الاحتياطي غير مدعوم بهذي البيئة — القاعدة مو ملف SQLite محلي. "
            "راجع تنبيه بند 34 بالإعدادات لخطة النسخ الاحتياطي المناسبة للإنتاج."
        ))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"farm_system_{stamp}.db"
    shutil.copyfile(db_path, os.path.join(_backup_dir(), filename))
    return filename


def list_backups() -> list[dict]:
    d = _backup_dir()
    rows = []
    for name in os.listdir(d):
        if not name.endswith(".db"):
            continue
        full = os.path.join(d, name)
        stat = os.stat(full)
        rows.append({
            "filename": name,
            "size_kb": round(stat.st_size / 1024, 1),
            "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
        })
    rows.sort(key=lambda r: r["created_at"], reverse=True)
    return rows


def resolve_backup_path(filename: str) -> str | None:
    """يرجّع المسار الكامل لملف نسخة احتياطية لو كان فعلاً داخل مجلد
    النسخ (يمنع محاولة الوصول لملفات ثانية بالاسم — path traversal)."""
    backups_dir = os.path.realpath(_backup_dir())
    candidate = os.path.realpath(os.path.join(backups_dir, os.path.basename(filename)))
    if not candidate.startswith(backups_dir + os.sep) or not os.path.isfile(candidate):
        return None
    return candidate


def _json_safe(value):
    """تحويل قيم SQLAlchemy الشائعة (تاريخ/وقت/Decimal/bytes) لصيغة
    JSON قابلة للتخزين — نفس القيمة الأصلية تُستنتَج عكسياً وقت
    الاستيراد لاحقاً (تواريخ/أوقات بصيغة ISO قياسية)."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    return str(value)


def export_all_tables_json() -> io.BytesIO:
    """تصدير كل جدول بقاعدة البيانات الحالية لملف JSON وحيد — يشتغل
    بأي محرّك قاعدة بيانات (SQLite أو PostgreSQL) بدون أي فرق، لأنه
    يعتمد على SQLAlchemy Core مباشرة (`db.metadata`) مو أدوات خاصة
    بمحرّك معيّن. يُبنى بالكامل بالذاكرة ويُرجَّع مباشرة للتنزيل —
    صفر تخزين بملفات السيرفر (بيئات الاستضافة المُدارة زي Render غالباً
    تمسح أي ملف محلي عند كل إعادة نشر، فتخزين محلي هنا كان بلا فايدة
    فعلية أصلاً)."""
    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "app": "مراح بو علي",
        "tables": {},
    }
    with db.engine.connect() as conn:
        for table in db.metadata.sorted_tables:
            rows = conn.execute(table.select()).mappings().all()
            payload["tables"][table.name] = [
                {col: _json_safe(val) for col, val in row.items()} for row in rows
            ]
    buf = io.BytesIO(json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8"))
    buf.seek(0)
    return buf
