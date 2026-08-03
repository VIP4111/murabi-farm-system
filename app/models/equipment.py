from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class Equipment(db.Model):
    """قطعة/صنف معدات المزرعة (بند إضافي 108) — نفس نمط `Feed`/`Pharmacy`
    بالضبط (رصيد + حركات وارد/صادر)، عشان مستودع المعدات يستخدم نفس
    شاشة "المستودع" بالتطبيق (استهلاك/متبقي/نسبة استهلاك) اللي طلبها
    المالك لأبوه — بدون أي منطق جديد، إعادة استخدام كاملة."""
    __tablename__ = "equipment_items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(80))  # أدوات يدوية / أجهزة / قطع غيار...
    unit = db.Column(db.String(32), default="قطعة")
    unit_price = db.Column(db.Float)
    available_qty = db.Column(db.Float, default=0)
    min_stock_qty = db.Column(db.Float, default=0)

    status = db.Column(db.String(32), default="active", nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)

    def deduct_stock(self, qty: float) -> None:
        """نفس قيد `Feed.deduct_stock`/`Pharmacy.deduct_stock` — سحب سالب
        ممنوع، يرفض العملية كاملة بدل القصّ الصامت."""
        available = self.available_qty or 0
        if qty > available:
            raise ValueError(
                f'الكمية المطلوبة ({qty}) أكبر من المتوفر فعلياً من "{self.name}" '
                f'({available}) — حدّث المخزون أولاً أو قلّل الكمية.'
            )
        self.available_qty = available - qty

    def add_stock(self, qty: float) -> None:
        self.available_qty = (self.available_qty or 0) + qty


class EquipmentMovement(db.Model):
    """حركة مخزون معدات — وارد (شراء) أو صادر (استهلاك/تلف/فقد) — نفس
    بنية `FeedMovement` بالضبط."""
    __tablename__ = "equipment_movements"

    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey("equipment_items.id"), nullable=False)
    equipment = db.relationship("Equipment")

    movement_type = db.Column(db.String(16), nullable=False)  # in / out
    quantity = db.Column(db.Float, nullable=False)
    before_qty = db.Column(db.Float)
    after_qty = db.Column(db.Float)

    barn_id = db.Column(db.Integer, db.ForeignKey("barns.id"), nullable=True)
    barn = db.relationship("Barn")

    note = db.Column(db.Text)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=_now)
