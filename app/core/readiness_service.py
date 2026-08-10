"""
فحص "استكمال البيانات والجاهزية" قبل النشر الفعلي (بند 33 بالمواصفة
الرئيسية) — قائمة تحقق آلية لنقاط شائعة تُنسى قبل تشغيل النظام على قطيع
حقيقي، بدل ما يكتشفها المستخدم بالطريقة الصعبة بعد الاعتماد عليه.

كل فحص يرجّع حالة (ok/warning/critical) + تسمية + تفصيل، بدون أي تعديل
تلقائي على البيانات — عرض فقط، والقرار يبقى لصاحب الحلال.
"""
from flask import current_app
from flask_babel import gettext as _
from app.models import User, Barn, Animal, Pharmacy
from app.core import backup_service


def run_checks() -> list[dict]:
    checks = []

    owner = User.query.filter_by(phone=current_app.config["OWNER_PHONE"]).first()
    if owner and owner.check_password("change-me-123"):
        checks.append({
            "level": "critical", "label": _("كلمة مرور المالك الافتراضية"),
            "detail": _("لسا ما غيّرتها من القيمة الافتراضية — أول شي تسويه قبل أي استخدام فعلي."),
        })
    else:
        checks.append({"level": "ok", "label": _("كلمة مرور المالك"), "detail": _("تم تغييرها عن الافتراضي.")})

    if current_app.config.get("SECRET_KEY") == "dev-secret-change-me":
        checks.append({
            "level": "critical", "label": _("SECRET_KEY الافتراضي"),
            "detail": _("لسا القيمة الافتراضية بملف .env — لازم تغييرها قبل أي نشر فعلي (تؤثر على أمان جلسات الدخول)."),
        })
    else:
        checks.append({"level": "ok", "label": "SECRET_KEY", "detail": _("تم تخصيصه.")})

    if not current_app.config.get("SESSION_COOKIE_SECURE"):
        checks.append({
            "level": "warning", "label": _("أمان كوكي الجلسة"),
            "detail": _("SESSION_COOKIE_SECURE غير مفعّل — طبيعي محلياً/بالمعاينة، لكن لازم يكون مفعّل تلقائياً على Render (بند 87)."),
        })
    else:
        checks.append({"level": "ok", "label": _("أمان كوكي الجلسة"), "detail": _("مفعّل — كوكي الدخول ما تُرسَل إلا عبر HTTPS.")})

    if current_app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:"):
        checks.append({
            "level": "warning", "label": _("قاعدة البيانات SQLite"),
            "detail": _("مناسبة للتطوير حالياً — راجع خطة الترقية لـPostgreSQL بـROADMAP.md قبل الإنتاج الفعلي (تغيير DATABASE_URL بس)."),
        })
    else:
        checks.append({"level": "ok", "label": _("قاعدة البيانات"), "detail": _("PostgreSQL أو ما يعادلها.")})

    isolation_barn = Barn.query.filter_by(barn_type="عزل").first()
    if not isolation_barn:
        checks.append({
            "level": "warning", "label": _("حظيرة العزل"),
            "detail": _("ما فيه حظيرة بنوع \"عزل\" بعد — خطة العزل التلقائي بعد الولادة (بند 4) تحتاجها لتنقل الأم والمولود تلقائياً."),
        })
    else:
        checks.append({"level": "ok", "label": _("حظيرة العزل"), "detail": _("موجودة (%(name)s).", name=isolation_barn.barn_name)})

    no_barn = Animal.query.filter_by(status="active", barn_id=None).count()
    if no_barn:
        checks.append({"level": "warning", "label": _("حيوانات بدون حظيرة"), "detail": _("%(n)s رأس نشط بدون حظيرة معيّنة.", n=no_barn)})
    else:
        checks.append({"level": "ok", "label": _("تعيين الحظائر"), "detail": _("كل الرؤوس النشطة لها حظيرة.")})

    no_birth_date = Animal.query.filter_by(status="active").filter(Animal.birth_date.is_(None)).count()
    if no_birth_date:
        checks.append({
            "level": "warning", "label": _("تاريخ ميلاد ناقص"),
            "detail": _("%(n)s رأس نشط بدون تاريخ ميلاد — يأثّر على فلاتر البهم/قريب الولادة/العمر (بند 8).", n=no_birth_date),
        })
    else:
        checks.append({"level": "ok", "label": _("تاريخ الميلاد"), "detail": _("مكتمل لكل الرؤوس النشطة.")})

    active_users = User.query.filter_by(is_active_account=True).count()
    if active_users <= 1:
        checks.append({
            "level": "warning", "label": _("فريق العمل"),
            "detail": _("ما فيه إلا حساب المالك — أضف حسابات الفريق الفعلي (دكتور/عمال) قبل التشغيل اليومي."),
        })
    else:
        checks.append({"level": "ok", "label": _("فريق العمل"), "detail": _("%(n)s حساب نشط.", n=active_users)})

    if not Pharmacy.query.first():
        checks.append({"level": "warning", "label": _("الصيدلية"), "detail": _("ما فيه أي دواء مسجّل بعد.")})
    else:
        checks.append({"level": "ok", "label": _("الصيدلية"), "detail": _("فيها أدوية مسجّلة.")})

    if backup_service.is_backup_supported():
        if backup_service.list_backups():
            checks.append({"level": "ok", "label": _("النسخ الاحتياطي"), "detail": _("فيه نسخة احتياطية واحدة على الأقل (بند 34).")})
        else:
            checks.append({
                "level": "warning", "label": _("النسخ الاحتياطي"),
                "detail": _("ما أخذت أي نسخة احتياطية بعد — راجع \"النسخ الاحتياطي\" بشاشة الإعدادات (بند 34)."),
            })

    return checks
