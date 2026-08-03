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
