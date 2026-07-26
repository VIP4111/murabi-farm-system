"""
فحص "استكمال البيانات والجاهزية" قبل النشر الفعلي (بند 33 بالمواصفة
الرئيسية) — قائمة تحقق آلية لنقاط شائعة تُنسى قبل تشغيل النظام على قطيع
حقيقي، بدل ما يكتشفها المستخدم بالطريقة الصعبة بعد الاعتماد عليه.

كل فحص يرجّع حالة (ok/warning/critical) + تسمية + تفصيل، بدون أي تعديل
تلقائي على البيانات — عرض فقط، والقرار يبقى لصاحب الحلال.
"""
from flask import current_app
from app.models import User, Barn, Animal, Pharmacy
from app.core import backup_service


def run_checks() -> list[dict]:
    checks = []

    owner = User.query.filter_by(phone=current_app.config["OWNER_PHONE"]).first()
    if owner and owner.check_password("change-me-123"):
        checks.append({
            "level": "critical", "label": "كلمة مرور المالك الافتراضية",
            "detail": "لسا ما غيّرتها من القيمة الافتراضية — أول شي تسويه قبل أي استخدام فعلي.",
        })
    else:
        checks.append({"level": "ok", "label": "كلمة مرور المالك", "detail": "تم تغييرها عن الافتراضي."})

    if current_app.config.get("SECRET_KEY") == "dev-secret-change-me":
        checks.append({
            "level": "critical", "label": "SECRET_KEY الافتراضي",
            "detail": "لسا القيمة الافتراضية بملف .env — لازم تغييرها قبل أي نشر فعلي (تؤثر على أمان جلسات الدخول).",
        })
    else:
        checks.append({"level": "ok", "label": "SECRET_KEY", "detail": "تم تخصيصه."})

    if current_app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:"):
        checks.append({
            "level": "warning", "label": "قاعدة البيانات SQLite",
            "detail": "مناسبة للتطوير حالياً — راجع خطة الترقية لـPostgreSQL بـROADMAP.md قبل الإنتاج الفعلي (تغيير DATABASE_URL بس).",
        })
    else:
        checks.append({"level": "ok", "label": "قاعدة البيانات", "detail": "PostgreSQL أو ما يعادلها."})

    isolation_barn = Barn.query.filter_by(barn_type="عزل").first()
    if not isolation_barn:
        checks.append({
            "level": "warning", "label": "حظيرة العزل",
            "detail": "ما فيه حظيرة بنوع \"عزل\" بعد — خطة العزل التلقائي بعد الولادة (بند 4) تحتاجها لتنقل الأم والمولود تلقائياً.",
        })
    else:
        checks.append({"level": "ok", "label": "حظيرة العزل", "detail": f"موجودة ({isolation_barn.barn_name})."})

    no_barn = Animal.query.filter_by(status="active", barn_id=None).count()
    if no_barn:
        checks.append({"level": "warning", "label": "حيوانات بدون حظيرة", "detail": f"{no_barn} رأس نشط بدون حظيرة معيّنة."})
    else:
        checks.append({"level": "ok", "label": "تعيين الحظائر", "detail": "كل الرؤوس النشطة لها حظيرة."})

    no_birth_date = Animal.query.filter_by(status="active").filter(Animal.birth_date.is_(None)).count()
    if no_birth_date:
        checks.append({
            "level": "warning", "label": "تاريخ ميلاد ناقص",
            "detail": f"{no_birth_date} رأس نشط بدون تاريخ ميلاد — يأثّر على فلاتر البهم/قريب الولادة/العمر (بند 8).",
        })
    else:
        checks.append({"level": "ok", "label": "تاريخ الميلاد", "detail": "مكتمل لكل الرؤوس النشطة."})

    active_users = User.query.filter_by(is_active_account=True).count()
    if active_users <= 1:
        checks.append({
            "level": "warning", "label": "فريق العمل",
            "detail": "ما فيه إلا حساب المالك — أضف حسابات الفريق الفعلي (دكتور/عمال) قبل التشغيل اليومي.",
        })
    else:
        checks.append({"level": "ok", "label": "فريق العمل", "detail": f"{active_users} حساب نشط."})

    if not Pharmacy.query.first():
        checks.append({"level": "warning", "label": "الصيدلية", "detail": "ما فيه أي دواء مسجّل بعد."})
    else:
        checks.append({"level": "ok", "label": "الصيدلية", "detail": "فيها أدوية مسجّلة."})

    if backup_service.is_backup_supported():
        if backup_service.list_backups():
            checks.append({"level": "ok", "label": "النسخ الاحتياطي", "detail": "فيه نسخة احتياطية واحدة على الأقل (بند 34)."})
        else:
            checks.append({
                "level": "warning", "label": "النسخ الاحتياطي",
                "detail": "ما أخذت أي نسخة احتياطية بعد — راجع \"النسخ الاحتياطي\" بشاشة الإعدادات (بند 34).",
            })

    return checks
