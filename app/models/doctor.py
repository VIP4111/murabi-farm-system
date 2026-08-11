from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class Doctor(db.Model):
    __tablename__ = "doctors"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(32))
    specialty = db.Column(db.String(120))
    status = db.Column(db.String(32), default="active", nullable=False)

    # دليل التواصل البيطري المحلي (بند إضافي 171) — `is_external=True`
    # يميّز طبيب/عيادة خارجية (مرجع طوارئ فقط، لا حساب دخول بالنظام)
    # عن الطبيب الداخلي بفريق العمل (له أصلاً حساب `User` مستقل). حقول
    # وصفية بس، بدون أي منطق آلي مرتبط بها.
    is_external = db.Column(db.Boolean, default=False, nullable=False)
    clinic_name = db.Column(db.String(160))
    area = db.Column(db.String(160))
    notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=_now)
