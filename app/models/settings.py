from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class ServiceToggle(db.Model):
    """
    "مركز تحكم الخدمات" اللي يشوفه المالك بالإعدادات: كل ميزة اختيارية
    (CRM، تعدد الفروع، تعدد اللغات، ...) لها سطر هنا مع حالة تفعيل ونص
    "النشرة" اللي يشرح شروط تفعيلها. الميزة الموقوفة تختفي بالكامل من كل
    واجهات النظام (مو بس تُخفى بصرياً).
    """
    __tablename__ = "service_toggles"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    requirements_note = db.Column(db.Text)  # نص "النشرة" قبل التفعيل
    is_enabled = db.Column(db.Boolean, default=False, nullable=False)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)
