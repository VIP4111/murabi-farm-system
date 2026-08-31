"""إشعار تيليجرام فوري لنقص مخزون حرج (بند إضافي 162، المرحلة د-1) —
طلبك: بدل ما تعرف بالنقص من تقرير دوري أو تفتح التطبيق، يوصلك إشعار
لحظي وقت ما المخزون فعلاً يهبط تحت الحد الأدنى (`min_stock_qty`).

**تنبيه تنبؤي (بند إضافي 237)**: الحد الأدنى الثابت وحده ما يكفي —
صنف بكمية أكبر من الحد الأدنى ممكن ينفد خلال أيام لو معدل استهلاكه
الأخير عالي (بند 3 من خطة الأتمتة الواقعية: "نقص مخزون تنبؤي" بدل حد
ثابت). نفس نقطة الاستدعاء بالضبط (بعد أي `deduct_stock()` فعلي)، بس
الآن نفحص الاثنين معاً: هل تحت الحد الأدنى، أو هل باقي أيام أقل من
`predictive_stock_alert_days` حسب معدل الاستهلاك الفعلي؟"""
from flask_babel import gettext as _, force_locale
from app.core import telegram_service


def _notify(kind_label, icon: str, item, permission_code: str, days_until_stockout: float | None) -> None:
    from app.models import FarmSettings
    fs = FarmSettings.get()
    min_qty = item.min_stock_qty or 0
    available = item.available_qty or 0

    under_min = min_qty > 0 and available <= min_qty
    running_out_soon = (
        days_until_stockout is not None and days_until_stockout <= fs.predictive_stock_alert_days
    )
    if not under_min and not running_out_soon:
        return

    # بند إضافي (2026-08-31) — نفس فجوة "تعدد المستلمين بلغات مختلفة"
    # المعالَجة بالتقرير اليومي — نص منفصل لكل لغة موجودة فعلياً بين
    # المستلمين، بدل نسخة واحدة (كانت بالعربي دايماً، بلا سياق طلب هنا).
    from app.models import User
    recipients = [
        u for u in User.query.filter(User.telegram_chat_id.isnot(None), User.is_active_account.is_(True)).all()
        if u.has_permission(permission_code)
    ]
    for lang in {u.language or "ar" for u in recipients}:
        with force_locale(lang):
            if under_min:
                reason = _("متبقي %(available)s %(unit)s (الحد الأدنى %(min)s %(unit)s)",
                           available=available, unit=item.unit or "", min=min_qty)
            else:
                reason = _(
                    "متبقي %(available)s %(unit)s — على معدل الاستهلاك الأخير، "
                    "يكفي ~%(days)s يوم بس (أقل من %(threshold)s يوم)",
                    available=available, unit=item.unit or "",
                    days=days_until_stockout, threshold=fs.predictive_stock_alert_days,
                )
            text = _("📦 نقص مخزون %(kind)s %(icon)s", kind=_(kind_label), icon=icon) + f"\n{item.name}: {reason}"
        for user in recipients:
            if (user.language or "ar") == lang:
                telegram_service.notify_user(user, text)


def check_pharmacy_stock(pharmacy) -> None:
    from app.health.health_service import pharmacy_days_until_stockout
    _notify("دواء", "💊", pharmacy, "pharmacy.manage", pharmacy_days_until_stockout(pharmacy))


def check_feed_stock(feed) -> None:
    from app.feed.feed_service import days_until_stockout
    _notify("علف", "🌾", feed, "feed.manage", days_until_stockout(feed))
