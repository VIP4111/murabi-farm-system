from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class MilkRecord(db.Model):
    """سجل حليب (بند 14 بالمواصفة) — قيد واحد لكل حلبة (جلسة صباح/مساء)."""
    __tablename__ = "milk_records"

    id = db.Column(db.Integer, primary_key=True)
    animal_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=False)
    animal = db.relationship("Animal")

    date = db.Column(db.Date, nullable=False)
    session = db.Column(db.String(16), nullable=False)  # صباح / مساء
    quantity_liters = db.Column(db.Float, nullable=False)
    notes = db.Column(db.String(255))

    recorded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    recorded_by = db.relationship("User")

    created_at = db.Column(db.DateTime, default=_now)
