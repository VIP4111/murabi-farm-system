from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class EmployeeOfMonth(db.Model):
    """موظف الشهر (بند إضافي 239) — يُختار تلقائياً بأول تسجيل دخول
    بعد بداية شهر جديد، باستخدام نفس محرك تقييم الأداء الموضوعي
    (`app/team/performance_service.worker_performance`) على الشهر
    السابق كامل. يبقى `pending_confirmation` لين يراجعه صاحب الحلال
    ويحدد مبلغ المكافأة ويأكّد — عندها بس تتسجل حركة مالية فعلية
    ويتحول لـ`confirmed`."""
    __tablename__ = "employee_of_month"

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user = db.relationship("User", foreign_keys=[user_id])
    score = db.Column(db.Float, nullable=False)

    status = db.Column(db.String(24), default="pending_confirmation", nullable=False)
    # pending_confirmation / confirmed

    bonus_amount = db.Column(db.Float, nullable=True)
    finance_id = db.Column(db.Integer, db.ForeignKey("finance.id"), nullable=True)
    finance = db.relationship("Finance")

    confirmed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    confirmed_by = db.relationship("User", foreign_keys=[confirmed_by_id])
    confirmed_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=_now)

    __table_args__ = (db.UniqueConstraint("year", "month", name="uq_employee_of_month_period"),)
