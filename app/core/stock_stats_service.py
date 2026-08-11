"""استهلاك يوم/شهر لأي صنف مخزون (بند إضافي 108) — لشاشة "المستودع"
المبسّطة (`/family-view`). العلف له سجل حركات فعلي (`FeedMovement`)،
الدواء ما له سجل حركات مباشر — يُحسب من نفس مصدر بند 95 (تقرير طلب
الشراء): مجموع `quantity_used` بسجلات الزيارة/المرض/التطعيم."""
from datetime import date, timedelta

from app.extensions import db
from app.models import FeedMovement, VetVisit, Disease, Vaccination


def feed_consumption_stats(feed, *, day_lookback: int = 1, month_lookback: int = 30) -> dict:
    def _consumed_since(days):
        since = date.today() - timedelta(days=days)
        return (db.session.query(db.func.coalesce(db.func.sum(FeedMovement.quantity), 0))
                .filter(FeedMovement.feed_id == feed.id, FeedMovement.movement_type == "out",
                        FeedMovement.created_at >= since)
                .scalar()) or 0
    return {"consumed_day": _consumed_since(day_lookback), "consumed_month": _consumed_since(month_lookback)}


def stock_alert_level(item, stats, *, target_days: int = 30, red_days: int = 7, today=None) -> dict:
    """مستوى تنبيه أحمر/أصفر/أخضر لأي صنف مخزون (بند إضافي 196) — يُستخدم
    لعلف/دواء/معدات بنفس الشاشة. المعدل اليومي يُحسب من استهلاك الشهر
    الحالي مقسوماً على عدد الأيام من بداية الشهر (وليس ثابتاً /30)، حسب
    طلب المستخدم صراحة: لو اليوم هو أول يوم بالشهر، يُحسب على أساس يوم
    واحد بدل القسمة على صفر."""
    today = today or date.today()
    available = item.available_qty or 0
    min_qty = item.min_stock_qty or 0
    days_elapsed = max(today.day, 1)
    daily_rate = (stats.get("consumed_month") or 0) / days_elapsed

    if daily_rate <= 0:
        return {"level": "green", "daily_rate": 0, "days_remaining": None, "until_date": None, "buy_qty": None}

    days_remaining = available / daily_rate
    if available <= min_qty or days_remaining <= red_days:
        buy_qty = max(daily_rate * target_days - available, 0)
        return {
            "level": "red", "daily_rate": round(daily_rate, 2), "days_remaining": round(days_remaining, 1),
            "until_date": None, "buy_qty": round(buy_qty, 1),
        }

    until_date = today + timedelta(days=int(days_remaining))
    level = "yellow" if days_remaining <= target_days else "green"
    return {
        "level": level, "daily_rate": round(daily_rate, 2), "days_remaining": round(days_remaining, 1),
        "until_date": until_date, "buy_qty": None,
    }


def pharmacy_consumption_stats(pharmacy, *, day_lookback: int = 1, month_lookback: int = 30) -> dict:
    def _consumed_since(days):
        since = date.today() - timedelta(days=days)
        total = 0
        for model in (VetVisit, Disease, Vaccination):
            total += (db.session.query(db.func.coalesce(db.func.sum(model.quantity_used), 0))
                      .filter(model.pharmacy_id == pharmacy.id, model.date >= since)
                      .scalar()) or 0
        return total
    return {"consumed_day": _consumed_since(day_lookback), "consumed_month": _consumed_since(month_lookback)}
