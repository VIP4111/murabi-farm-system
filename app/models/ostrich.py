from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class Incubator(db.Model):
    """حاضنة/علبة تفقيس فعلية بالمزرعة — وحدة مادية تُحمَّل بيض النعام."""
    __tablename__ = "incubators"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False)
    name = db.Column(db.String(120))
    capacity = db.Column(db.Integer)
    status = db.Column(db.String(16), default="active", nullable=False)  # active/inactive

    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)


class OstrichEgg(db.Model):
    """
    سجل بيضة نعام واحدة — نقطة الدخول الموحّدة لدورة (بيض → حضانة → فقس).
    نفس البيضة تُحدَّث بمكانها (بدون جدول "دفعة تفقيس" منفصل) عشان تتبّع
    كل بيضة بمفردها من الإنتاج لين الفقس أو الفشل.
    """
    __tablename__ = "ostrich_eggs"

    id = db.Column(db.Integer, primary_key=True)
    mother_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=False)
    mother = db.relationship("Animal", foreign_keys=[mother_id])

    lay_date = db.Column(db.Date, nullable=False)
    quality = db.Column(db.String(16))  # ممتاز/جيد/متوسط/مرفوض
    weight_grams = db.Column(db.Float)
    notes = db.Column(db.Text)

    incubator_id = db.Column(db.Integer, db.ForeignKey("incubators.id"), nullable=True)
    incubator = db.relationship("Incubator")
    incubation_start_date = db.Column(db.Date)

    hatch_result = db.Column(db.String(16), default="pending", nullable=False)  # pending/hatched/failed
    actual_hatch_date = db.Column(db.Date)
    fail_reason = db.Column(db.Text)

    hatched_animal_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=True)
    hatched_animal = db.relationship("Animal", foreign_keys=[hatched_animal_id])

    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)
