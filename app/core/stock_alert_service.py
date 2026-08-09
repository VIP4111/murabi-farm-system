"""إشعار تيليجرام فوري لنقص مخزون حرج (بند إضافي 162، المرحلة د-1) —
طلبك: بدل ما تعرف بالنقص من تقرير دوري أو تفتح التطبيق، يوصلك إشعار
لحظي وقت ما المخزون فعلاً يهبط تحت الحد الأدنى (`min_stock_qty`).

يُستدعى مباشرة بعد أي `deduct_stock()` فعلي (صيدلية بند 100، علف بند
178) — نفس فلسفة إشعارات البلاغات (بند 159): فشل الإرسال بصمت، صفر
تأثير على العملية الأساسية (سحب المخزون نفسه)."""
from app.core import telegram_service


def _notify(kind_label: str, icon: str, item, permission_code: str) -> None:
    min_qty = item.min_stock_qty or 0
    if min_qty <= 0:
        return  # ما فيه حد أدنى مضبوط أصلاً — لا أساس للمقارنة
    available = item.available_qty or 0
    if available > min_qty:
        return

    from app.models import User
    for user in User.query.filter(User.telegram_chat_id.isnot(None), User.is_active_account.is_(True)).all():
        if user.has_permission(permission_code):
            telegram_service.notify_user(
                user,
                f"📦 نقص مخزون {kind_label} {icon}\n"
                f"{item.name}: متبقي {available} {item.unit or ''} "
                f"(الحد الأدنى {min_qty} {item.unit or ''})",
            )


def check_pharmacy_stock(pharmacy) -> None:
    _notify("دواء", "💊", pharmacy, "pharmacy.manage")


def check_feed_stock(feed) -> None:
    _notify("علف", "🌾", feed, "feed.manage")
