"""
تشيك-ليست تهيئة النظام بالصفحة الرئيسية (بند إضافي، 2026-07-27) — تظهر
لصاحب الحلال فقط، ويتحقق كل بند فيها تلقائياً من وجود بيانات فعلية
(حظيرة/حيوان/عامل/دواء/علف)، بدون أي تعليم يدوي. تختفي نهائياً بعد ما
يضغط "تجاهل" (FarmSettings.setup_checklist_dismissed) — طلب صريح من
صاحب النظام: الأزرار السريعة الموجودة أصلاً كافية بعد أول مرة.
"""
from flask_babel import gettext as _
from app.models import Animal, Barn, Pharmacy, Feed, User


def get_setup_checklist_items() -> list[dict]:
    return [
        {"label": _("أضف أول حظيرة"), "done": Barn.query.count() > 0, "endpoint": "core.barns_new"},
        {"label": _("أضف أول رأس"), "done": Animal.query.count() > 0, "endpoint": "core.animals_new"},
        {"label": _("أضف عضو فريق (عامل/دكتور)"), "done": User.query.count() > 1, "endpoint": "team.members_new"},
        {"label": _("أضف أول دواء بالصيدلية"), "done": Pharmacy.query.count() > 0, "endpoint": "health.pharmacy_new"},
        {"label": _("أضف أول صنف علف"), "done": Feed.query.count() > 0, "endpoint": "feed.items_new"},
    ]


def all_done(items: list[dict]) -> bool:
    return all(i["done"] for i in items)
