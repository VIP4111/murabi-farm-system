from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class AnimalWeight(db.Model):
    """سجل وزن تاريخي لحيوان — كل قيد هنا نقطة قياس بتاريخ معيّن. آخر قيد
    (بالتاريخ) يُنسخ تلقائياً لحقل `Animal.weight` عشان بوابات محرك الدورة
    وحاسبة العلف (اللي تعتمد على وزن حالي واحد) يستمرون يشتغلون بدون تعديل."""
    __tablename__ = "animal_weights"

    id = db.Column(db.Integer, primary_key=True)
    animal_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=False)
    animal = db.relationship("Animal")

    date = db.Column(db.Date, nullable=False)
    weight = db.Column(db.Float, nullable=False)
    notes = db.Column(db.String(255))

    recorded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    recorded_by = db.relationship("User")

    created_at = db.Column(db.DateTime, default=_now)


class AnimalNote(db.Model):
    """ملاحظة حرة مرتبطة بحيوان — لتوثيق أي شيء ما إله جدول مخصص بعد."""
    __tablename__ = "animal_notes"

    id = db.Column(db.Integer, primary_key=True)
    animal_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=False)
    animal = db.relationship("Animal")

    date = db.Column(db.Date, nullable=False)
    note = db.Column(db.Text, nullable=False)

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_by = db.relationship("User")

    created_at = db.Column(db.DateTime, default=_now)
