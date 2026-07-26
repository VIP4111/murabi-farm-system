from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class Finance(db.Model):
    """كل الحركات المالية: بيع، شراء، مصروف. لا تُحذف نهائياً أبداً — تُلغى
    (is_cancelled) عشان يضل سجل التدقيق كامل، بنفس مبدأ 'لا شيء يختفي بصمت'."""
    __tablename__ = "finance"

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    operation_type = db.Column(db.String(32), nullable=False)  # sale/purchase/expense
    category = db.Column(db.String(80))
    item = db.Column(db.String(160))
    description = db.Column(db.Text)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(32))

    related_animal_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=True)
    related_animal = db.relationship("Animal")

    # مصروف غير مباشر (بند إضافي، 2026-07-23) — إيجار/صيانة/رواتب...
    # مصروف عام يخص القطيع كله، مو حيوان محدد (`related_animal_id` يبقى
    # فاضي بهذي الحالة أصلاً). يُوزَّع بالتساوي على عدد الرؤوس النشطة
    # الحالي — نفس منهجية تقرير "تكلفة الرأس الشهرية" (بند 18) بالضبط،
    # وصار يُحتسب أيضاً كنصيب فردي بتقرير تكلفة الرأس الفردي (بند 45).
    is_indirect = db.Column(db.Boolean, default=False, nullable=False)

    is_cancelled = db.Column(db.Boolean, default=False, nullable=False)
    cancel_reason = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=_now)
