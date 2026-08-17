from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class InventoryCount(db.Model):
    """جرد فعلي لمخزون العلف/الدواء/المعدات (بند إضافي 208) — يقارن
    الكمية الفعلية الموزونة/المعدودة بالمستودع بالرصيد المحسوب أصلاً
    بالنظام (من حركات الشراء/الصرف)، ويصحح المخزون لهذا الرقم الفعلي
    تلقائياً. الفرق موجب (زيادة) يُعتبر تصحيح مخزون بس بدون أثر مالي؛
    الفرق سالب (نقص) يُسجَّل "هالك" — مصروف مالي غير مباشر (نفس آلية
    `Finance.is_indirect`) بقيمة الكمية الناقصة × سعر الوحدة المسجَّل
    بالصنف، فيُوزَّع تلقائياً على الرؤوس النشطة بنفس تقرير تكلفة الرأس
    الشهرية الموجود أصلاً (بند 18/45) — بدون أي منطق توزيع جديد."""
    __tablename__ = "inventory_counts"

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(16), nullable=False)  # feed / pharmacy / equipment
    item_id = db.Column(db.Integer, nullable=False)
    item_name = db.Column(db.String(160), nullable=False)  # صورة عن الاسم وقت الجرد

    count_date = db.Column(db.Date, nullable=False)
    expected_qty = db.Column(db.Float, nullable=False)
    actual_qty = db.Column(db.Float, nullable=False)
    diff_qty = db.Column(db.Float, nullable=False)  # actual - expected
    diff_value = db.Column(db.Float, nullable=True)  # قيمة الهالك (نقص فقط)

    finance_id = db.Column(db.Integer, db.ForeignKey("finance.id"), nullable=True)
    finance = db.relationship("Finance")

    note = db.Column(db.Text)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=_now)
