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
