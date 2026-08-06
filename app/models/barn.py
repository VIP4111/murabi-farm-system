from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class Barn(db.Model):
    __tablename__ = "barns"

    id = db.Column(db.Integer, primary_key=True)
    barn_no = db.Column(db.String(32), unique=True, nullable=False)
    barn_name = db.Column(db.String(120), nullable=False)
    barn_type = db.Column(db.String(64))  # عادية / عزل / نفاس ... إلخ
    capacity = db.Column(db.Integer)

    # العامل المسؤول عن هالحظيرة — أساس توجيه المهام التلقائي (مرحلة 5)
    responsible_worker_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    responsible_worker = db.relationship("User")

    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)

    animals = db.relationship("Animal", back_populates="barn")
    feeding_schedules = db.relationship(
        "BarnFeedingSchedule", back_populates="barn",
        order_by="BarnFeedingSchedule.sort_order", cascade="all, delete-orphan",
    )


class BarnFeedingSchedule(db.Model):
    """موعد وجبة علف واحدة لحظيرة معيّنة (بند إضافي 131) — كل حظيرة
    تحدّد عدد ومواعيد وجباتها لحالها (قرارك الصريح: إعداد مستقل لكل
    حظيرة، مو رقم عام للمزرعة). عند وصول الموعد، يولّد النظام تلقائياً
    مهمة واحدة مجمَّعة (توزيع علف + تنظيف معالف + تغيير ماء) للعامل
    المسؤول عن الحظيرة — نفس فلسفة `daily_task_service.py` بالضبط
    (idempotent عبر source_id مبني من تجزئة رقمية، بدون Cron)."""
    __tablename__ = "barn_feeding_schedules"

    id = db.Column(db.Integer, primary_key=True)
    barn_id = db.Column(db.Integer, db.ForeignKey("barns.id"), nullable=False)
    barn = db.relationship("Barn", back_populates="feeding_schedules")

    meal_time = db.Column(db.Time, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=_now)
