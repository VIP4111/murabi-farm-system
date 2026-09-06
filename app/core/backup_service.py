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
import enum
import io
import json
import os
import shutil
from datetime import date, datetime, timezone, time
from decimal import Decimal
from flask import current_app
from flask_babel import gettext as _
from sqlalchemy import Date, DateTime, Enum as SAEnum, Integer, Time, text
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
    """تحويل قيم SQLAlchemy الشائعة (تاريخ/وقت/Decimal/bytes/Enum) لصيغة
    JSON قابلة للتخزين — نفس القيمة الأصلية تُستنتَج عكسياً وقت
    الاستيراد لاحقاً (تواريخ/أوقات بصيغة ISO قياسية).

    بند إصلاح (فحص "النسخ الاحتياطي والاسترجاع"، 2026-09-06) — أعمدة
    Enum (مثال: `Animal.source`) كانت تقع بـ`else: return str(value)`
    فتُخزَّن كنص "AnimalSource.PURCHASE" (تمثيل Python الخام) بدل
    "PURCHASE" (اسم العضو الفعلي اللي تتوقعه قاعدة البيانات) — أي محاولة
    استرجاع لاحقة كانت ستفشل بخطأ "قيمة Enum غير معروفة". لقيناها فقط
    لما بنينا الاسترجاع الفعلي أول مرة واختبرناه (round-trip حقيقي)،
    رغم إن دالة التصدير هذي شغّالة بالإنتاج من قبل."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, enum.Enum):
        return value.name
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


class InvalidBackupFile(ValueError):
    """ملف مرفوع للاسترجاع مو ملف نسخة احتياطية صالح (تنسيق export_all_tables_json)."""


def _restore_value(value, col_type):
    """عكس `_json_safe()` — يحوّل نصوص ISO المخزَّنة بملف الاسترجاع
    رجوع لكائنات Python الفعلية (تاريخ/وقت) حسب نوع العمود بقاعدة
    البيانات، عشان الإدراج عبر SQLAlchemy Core يشتغل صح بأي محرّك
    (خصوصاً PostgreSQL — أصرم من SQLite بمطابقة الأنواع)."""
    if value is None or not isinstance(value, str):
        return value
    if isinstance(col_type, SAEnum):
        # توافق عكسي لملفات نسخ احتياطية قديمة (صُدِّرت قبل إصلاح
        # `_json_safe` أعلاه) خزّنت قيمة Enum كتمثيل Python الخام
        # ("AnimalSource.PURCHASE") بدل الاسم وحده ("PURCHASE") —
        # نجرّد الجزء بعد آخر نقطة لو طابق أحد أعضاء الـEnum الفعليين.
        candidate = value.rsplit(".", 1)[-1]
        if candidate in col_type.enums:
            return candidate
        return value
    try:
        if isinstance(col_type, DateTime):
            return datetime.fromisoformat(value)
        if isinstance(col_type, Date):
            return date.fromisoformat(value)
        if isinstance(col_type, Time):
            return time.fromisoformat(value)
    except ValueError:
        return value
    return value


def _self_referencing_columns(table) -> list[str]:
    """أعمدة تشير لنفس الجدول (مثال حقيقي بالمشروع: `animals.mother_id`/
    `father_id` يشيران لجدول `animals` نفسه — نفس الملاحظة الموثَّقة
    بـ`factory_reset_service._wipe_all_tables`). صف يشير لصف ثانٍ بنفس
    الجدول لسا ما اتُدرج يكسر قيد المفتاح الأجنبي وقت الإدراج — الحل:
    تأجيل هذي الأعمدة لتمرير `UPDATE` ثانٍ بعد إدراج كل صفوف الجدول."""
    cols = []
    for col in table.columns:
        for fk in col.foreign_keys:
            if fk.column.table is table:
                cols.append(col.name)
                break
    return cols


def _reset_postgres_sequences(table_names: list[str]) -> None:
    """بعد استرجاع صفوف بمعرِّفات (id) صريحة محفوظة من قبل، عدّاد
    التسلسل التلقائي (SERIAL/IDENTITY) بـPostgreSQL ما يتقدَّم تلقائياً
    (الإدراج الصريح للـid يتخطّى العدّاد) — أي `INSERT` لاحق بدون id
    صريح (السلوك العادي بكل النظام) يصطدم بمعرِّف مستخدم أصلاً ويفشل.
    هذا يعيد ضبط كل عدّاد على أعلى id فعلي موجود بعد الاسترجاع. SQLite
    ما يحتاج هذا (`AUTOINCREMENT` يعتمد أصلاً على أعلى قيمة فعلية
    بالجدول، مو عدّاد منفصل)."""
    if db.engine.dialect.name != "postgresql":
        return
    for table in db.metadata.sorted_tables:
        if table.name not in table_names:
            continue
        pk_cols = list(table.primary_key.columns)
        if len(pk_cols) != 1 or not isinstance(pk_cols[0].type, Integer):
            continue
        pk_name = pk_cols[0].name
        # SAVEPOINT (مو commit/rollback على مستوى الجلسة كاملة) — لو
        # الجدول ما عنده تسلسل فعلي (id مو SERIAL/IDENTITY)،
        # pg_get_serial_sequence يرجّع NULL وsetval يفشل بخطأ حقيقي
        # يوقف أي معاملة Postgres لحد ما تُرجَّع؛ begin_nested() يعزل
        # هذا الفشل المحتمل بدل ما يمسح كل عمليات الاسترجاع (INSERT)
        # اللي سوّيناها بنفس الجلسة قبل هذي النقطة.
        try:
            with db.session.begin_nested():
                db.session.execute(text(
                    f'SELECT setval(pg_get_serial_sequence(:tbl, :col), '
                    f'COALESCE((SELECT MAX("{pk_name}") FROM "{table.name}"), 1), '
                    f'(SELECT MAX("{pk_name}") FROM "{table.name}") IS NOT NULL)'
                ), {"tbl": table.name, "col": pk_name})
        except Exception:
            pass


def import_all_tables_json(payload: dict) -> dict:
    """استرجاع كامل من ملف نسخة احتياطية (نفس تنسيق `export_all_tables_json`)
    — بند إصلاح فجوة حقيقية: كان فيه تصدير بس بدون أي طريقة ترجع الملف
    للنظام، رغم إن الواجهة نفسها تقول "هذا الملف ضمانتك الوحيدة".

    **مسح كامل ثم إدراج** (مو دمج/إضافة) — يمسح كل البيانات الحالية
    أولاً (نفس `factory_reset_service._wipe_all_tables`، يتعامل صح مع
    فرق SQLite/PostgreSQL بترتيب الحذف) ثم يُدرج كل صف من الملف بنفس
    ترتيب `db.metadata.sorted_tables` (يحترم اعتماديات المفاتيح الأجنبية
    بين الجداول المختلفة). الأعمدة ذاتية المرجعية (نفس الجدول) تُؤجَّل
    لتمرير `UPDATE` ثانٍ بعد إدراج كل الصفوف. يرجّع dict فيه عدد الصفوف
    المُدرجة لكل جدول — المستدعي يتكفّل بـ`commit()`."""
    if not isinstance(payload, dict) or not isinstance(payload.get("tables"), dict):
        raise InvalidBackupFile(_(
            "ملف النسخة الاحتياطية غير صالح — لازم يكون نفس الملف اللي نزّلته "
            'من زر "تنزيل نسخة احتياطية كاملة" بدون أي تعديل.'
        ))
    tables_data = payload["tables"]

    from app.core.factory_reset_service import _wipe_all_tables
    _wipe_all_tables()

    deferred_updates = []  # (table, pk_column_name, pk_value, {col: value})
    counts = {}
    for table in db.metadata.sorted_tables:
        rows = tables_data.get(table.name)
        if not rows:
            counts[table.name] = 0
            continue
        self_ref_cols = set(_self_referencing_columns(table))
        pk_cols = list(table.primary_key.columns)
        pk_name = pk_cols[0].name if len(pk_cols) == 1 else None

        to_insert = []
        for row in rows:
            clean_row = {}
            deferred = {}
            for col in table.columns:
                if col.name not in row:
                    continue
                value = _restore_value(row[col.name], col.type)
                if col.name in self_ref_cols and value is not None:
                    deferred[col.name] = value
                    clean_row[col.name] = None
                else:
                    clean_row[col.name] = value
            to_insert.append(clean_row)
            if deferred and pk_name:
                deferred_updates.append((table, pk_name, clean_row.get(pk_name), deferred))

        db.session.execute(table.insert(), to_insert)
        counts[table.name] = len(to_insert)

    for table, pk_name, pk_value, deferred in deferred_updates:
        pk_col = table.c[pk_name]
        db.session.execute(table.update().where(pk_col == pk_value).values(**deferred))

    db.session.flush()
    _reset_postgres_sequences([name for name, n in counts.items() if n])

    return counts
