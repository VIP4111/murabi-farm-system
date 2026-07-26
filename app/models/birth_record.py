from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class BirthRecord(db.Model):
    """قائمة تحقق صريحة عند تسجيل ولادة (بند 11 بالمواصفة) — صف واحد لكل
    مولود، حقول منفصلة موثّقة بدل ملاحظة حرة واحدة. اختيارية بالكامل
    (كل حقل Boolean قابل يبقى None = ما تحقق منه أحد بعد)."""
    __tablename__ = "birth_records"

    id = db.Column(db.Integer, primary_key=True)
    animal_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=False, unique=True)
    animal = db.relationship("Animal", backref=db.backref("birth_record", uselist=False))

    breathing_ok = db.Column(db.Boolean)
    standing_ok = db.Column(db.Boolean)
    colostrum_received = db.Column(db.Boolean)
    cord_treated = db.Column(db.Boolean)
    birth_defects = db.Column(db.Text)

    recorded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    recorded_by = db.relationship("User")

    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)
