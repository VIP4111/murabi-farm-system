"""
تشيك-ليست تهيئة النظام (بند إضافي، 2026-07-27) — يتحقق كل بند فيها
تلقائياً من وجود بيانات فعلية (حظيرة/حيوان/عامل/دواء/علف)، بدون أي
تعليم يدوي.

بند إضافي (2026-09-01، طلبك المباشر: "احتاج صفحة خاصة فيها أساسيات
بداية إنشاء المزرعة... تعطيني اياها بترتيب... زر قدام كل امر... وفي
الآخر رسالة مزرعتك جاهزة تبتدي فيها الآن") — هذي الخدمة كانت مبنية
من قبل لكن غير مستخدمة فعلياً بأي شاشة (يتيمة بالكود). وسّعناها بأيقونة
ووصف مبسّط لكل بند، وبنينا لها شاشة مخصَّصة (`/onboarding/setup-checklist`)
بدل ما تبقى معطَّلة."""
from flask import current_app, url_for
from flask_babel import gettext as _
from app.models import Animal, Barn, Pharmacy, Feed, User, FarmSettings


def get_setup_checklist_items(current_user=None) -> list[dict]:
    items = []
    if current_user is not None:
        default_pw = current_app.config.get("OWNER_PASSWORD", "change-me-123")
        items.append({
            "code": "password",
            "icon": "🔑",
            "label": _("غيّر كلمة مرور حسابك"),
            "description": _("لسا مستخدم كلمة المرور الافتراضية — أول شي غيّرها قبل أي استخدام فعلي."),
            "done": not current_user.check_password(default_pw),
            "endpoint": "team.members_edit",
            "endpoint_kwargs": {"user_id": current_user.id},
        })

    fs = FarmSettings.get()
    items.append({
        "code": "farm_identity",
        "icon": "🏡",
        "label": _("عبّي بيانات مزرعتك الأساسية"),
        "description": _("اسم المزرعة وجوالها وعنوانها — تظهر برأس فاتورة البيع لاحقاً."),
        "done": bool(fs and fs.farm_name),
        "endpoint": "core.settings_home",
    })

    items += [
        {
            "code": "first_barn",
            "icon": "🏚️",
            "label": _("أضف أول حظيرة"),
            "description": _("خصوصاً حظيرة عزل واحدة — العزل التلقائي بعد الولادة أو وصول حيوان جديد يحتاجها."),
            "done": Barn.query.count() > 0,
            "endpoint": "core.barns_new",
        },
        {
            "code": "first_animal",
            "icon": "🐑",
            "label": _("أضف أول رأس"),
            "description": _("رأس واحد على الأقل — أو استورد قطيعك الحالي دفعة وحدة."),
            "done": Animal.query.count() > 0,
            "endpoint": "core.animals_new",
        },
        {
            "code": "team_member",
            "icon": "👥",
            "label": _("أضف عضو فريق (عامل/دكتور)"),
            "description": _("كل عضو فريق يحتاج حساب مستقل — يقدر يسجّل ملاحظاته ومهامه بنفسه."),
            "done": User.query.count() > 1,
            "endpoint": "team.members_new",
        },
        {
            "code": "first_medicine",
            "icon": "💊",
            "label": _("أضف أول دواء بالصيدلية"),
            "description": _("يفعّل خصم المخزون التلقائي وتنبيهات النفاد لاحقاً."),
            "done": Pharmacy.query.count() > 0,
            "endpoint": "health.pharmacy_new",
        },
        {
            "code": "first_feed",
            "icon": "🌾",
            "label": _("أضف أول صنف علف"),
            "description": _("يفعّل خطط التغذية وحساب استهلاك العلف لكل حظيرة."),
            "done": Feed.query.count() > 0,
            "endpoint": "feed.items_new",
        },
        {
            "code": "first_backup",
            "icon": "📥",
            "label": _("خذ نسخة احتياطية أول مرة"),
            "description": _("عادة بسيطة تحميك من فقدان بياناتك بالكامل لو صار أي عطل بقاعدة البيانات."),
            "done": _has_first_backup(),
            "endpoint": "core.backup_list",
        },
    ]
    return items


def _has_first_backup() -> bool:
    from app.models import AuditLog
    return AuditLog.query.filter(
        AuditLog.action.in_(["backup.export_json", "backup.create"])
    ).first() is not None


def get_setup_checklist_items_with_urls(current_user=None) -> list[dict]:
    items = get_setup_checklist_items(current_user)
    for item in items:
        item["url"] = url_for(item["endpoint"], **item.get("endpoint_kwargs", {}))
    return items


def all_done(items: list[dict]) -> bool:
    return all(i["done"] for i in items)
