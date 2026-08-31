from datetime import datetime, timezone
from flask_babel import gettext as _
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
    # صورة الصنف (بند إضافي 199) — لشاشة العامل المبسّطة (بطاقات صور
    # بدل قوائم نصية)، نفس آلية الرفع المستخدمة لصور أدلة البلاغات.
    photo_url = db.Column(db.String(255))

    status = db.Column(db.String(32), default="active", nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)

    # بند إضافي 276 — طلبك الصريح: "ما بين عندي مين اخذ المعدة" + تتبّع
    # حالتها (سليمة/تحتاج صيانة) وقت التسليم ووقت الاستلام. يُرفع تلقائياً
    # لما أي حركة تُسجَّل بحالة "تحتاج صيانة"، ويُنزَّل يدوياً من شاشة
    # تعديل الصنف بعد ما تنصلح فعلياً (نفس نمط "علم يرفعه النظام، الإنسان
    # ينزّله" المستخدم بميزات ثانية بالمشروع).
    needs_maintenance = db.Column(db.Boolean, default=False, nullable=False)

    def deduct_stock(self, qty: float) -> None:
        """نفس قيد `Feed.deduct_stock`/`Pharmacy.deduct_stock` — سحب سالب
        ممنوع، يرفض العملية كاملة بدل القصّ الصامت."""
        available = self.available_qty or 0
        if qty > available:
            raise ValueError(_(
                'الكمية المطلوبة (%(qty)s) أكبر من المتوفر فعلياً من "%(name)s" '
                '(%(available)s) — حدّث المخزون أولاً أو قلّل الكمية.',
                qty=qty, name=self.name, available=available,
            ))
        self.available_qty = available - qty

    def add_stock(self, qty: float) -> None:
        self.available_qty = (self.available_qty or 0) + qty


class EquipmentMovement(db.Model):
    """حركة مخزون معدات — وارد (شراء) أو صادر — نفس بنية `FeedMovement`
    بالضبط، + تتبّع استعارة/استرجاع (بند إضافي 110). المعدات خلافاً
    للعلف/الدواء غالباً **تُستعار وترجع** (مقص، أداة) مو تُستهلك نهائياً
    — حركة "صادر" ممكن تكون استعارة (`borrowed_by_id` معبّى، `returned_at`
    فاضي لين ترجع) أو صرف نهائي عادي (الاثنين فاضيين، نفس السلوك القديم
    بدون تغيير)."""
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

    # استعارة/استرجاع (بند إضافي 110) — مين استلم القطعة ومتى ترجعها.
    # `borrowed_by_id` يُعبَّى بس لو حركة الصادر استعارة (مو صرف نهائي
    # لمواد استهلاكية زي المسامير). `returned_at` فاضي لين تُسجَّل
    # الإرجاع فعلياً — أي صف فيه `borrowed_by_id` بدون `returned_at`
    # يعني القطعة لسا عند حد.
    borrowed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    borrowed_by = db.relationship("User", foreign_keys=[borrowed_by_id])
    returned_at = db.Column(db.DateTime, nullable=True)
    # صرف نهائي (مواد استهلاكية) لا يُتوقّع رجوعه — يُستثنى من "قطع لسا
    # عند حد" حتى لو `borrowed_by_id` معبّى (بند 276: الاستلام صار
    # إلزامي لكل صادر، فـ`borrowed_by_id` لحاله ما عاد كافي للتمييز).
    no_return_expected = db.Column(db.Boolean, default=False, nullable=False)

    # حالة القطعة وقت التسليم ووقت الاستلام (بند إضافي 276، طلبك الصريح
    # "خيار سليمة او تحتاج صيانة... وقت التسليم وفي وقت الاستلام") —
    # 'good' أو 'needs_maintenance'. تُستخدم لمعرفة عند مين تعطّلت القطعة
    # (آخر شخص استلمها وقت ما صارت الحالة "تحتاج صيانة").
    condition_at_handout = db.Column(db.String(20), nullable=True)
    condition_at_return = db.Column(db.String(20), nullable=True)

    note = db.Column(db.Text)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=_now)
