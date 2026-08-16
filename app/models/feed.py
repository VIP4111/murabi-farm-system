from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class Feed(db.Model):
    """مكوّن علف واحد (خام أو منتج تجاري) — القيمة الغذائية تُدخل مرة واحدة
    من ملصق الكيس أو تحليل مخبري، وتُستخدم بعدها بحساب الوصفات تلقائياً."""
    __tablename__ = "feeds"

    # فئة العلف (بند إضافي 51) — قائمة ثابتة منفصلة عن `category` النصي
    # الحر أعلاه، عشان حارس منع الزيادة المفاجئة للمركزات (10% أسبوعياً)
    # يحتاج تمييزاً موثوقاً لا يعتمد على دقة كتابة من يدير المخزون.
    FEED_CLASSES = ["concentrate", "roughage", "mineral", "other"]
    FEED_CLASS_LABELS_AR = {
        "concentrate": "مركّز", "roughage": "خشن", "mineral": "معدني/أملاح", "other": "أخرى",
    }

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(80))  # مركّز / دريس / تبن / سيلاج / إضافات
    feed_class = db.Column(db.String(16))

    protein_percent = db.Column(db.Float)
    energy_kcal_per_kg = db.Column(db.Float)  # طاقة ممثلة تقريبية
    fiber_percent = db.Column(db.Float)
    calcium_percent = db.Column(db.Float)
    phosphorus_percent = db.Column(db.Float)

    # وسم معلوماتي: هل يحتوي هذا الصنف نحاساً مرتفعاً (بند إضافي 51).
    contains_high_copper = db.Column(db.Boolean, default=False, nullable=False)

    # قائمة وحدات ثابتة (بند إضافي 202) — كانت `unit` نص حر (تكتب "كجم"
    # أو "كيلو" أو "كيلوجرام" بنفسك)، وهذا كان يكسر فعلياً منطق اقتراح
    # "الأرخص بين الأصناف البديلة" بتقرير طلب الشراء (بند 156) — الكود
    # هناك يجمع الأصناف البديلة بشرط "نفس التصنيف ونفس الوحدة" حرفياً،
    # فصنفين نفس الوحدة الحقيقية لكن مكتوبة بصيغتين مختلفتين يُعامَلان
    # كوحدتين مختلفتين بالغلط، ويفشل التجميع بصمت. القيمة المخزَّنة تبقى
    # عربي مباشر (بدل رمز إنجليزي + قاموس ترجمة) عمداً — كل الشاشات
    # الحالية تعرض `item.unit` مباشرة بدون أي فلتر، فتغيير التخزين لرمز
    # يكسرها كلها؛ الفورم بس يتحوّل من حقل نص حر لقائمة ثابتة بنفس
    # القيم العربية، صفر تغيير على أي شاشة عرض.
    UNITS = ["كجم", "طن", "لتر", "مل", "كيس", "ربطة"]

    unit = db.Column(db.String(32), default="كجم")
    # الوزن التقريبي للوحدة الواحدة بالكيلوجرام (بند إضافي 202) — مفيد
    # لوحدات العدّ اللي وزنها مو ثابت عالمياً (ربطة برسيم، كيس) عشان
    # صاحب الحلال يقدر يرجع لمرجع "كم كيلو بالربطة" وقت الشراء، بدون ما
    # نجبره يحوّل كل شي لكجم بالنظام نفسه. اختياري تماماً، وصفي بس —
    # ما يُستخدم بأي حساب تلقائي حالياً.
    unit_weight_kg = db.Column(db.Float)
    unit_price = db.Column(db.Float)
    available_qty = db.Column(db.Float, default=0)
    min_stock_qty = db.Column(db.Float, default=0)

    status = db.Column(db.String(32), default="active", nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)

    def deduct_stock(self, qty: float) -> None:
        """سحب سالب ممنوع (بند إضافي، 2026-07-23) — نفس قيد `Pharmacy.deduct_stock`،
        كان يُقصّ عند الصفر بصمت فيسجّل استهلاك أكبر من المخزون الفعلي."""
        available = self.available_qty or 0
        if qty > available:
            raise ValueError(
                f'الكمية المطلوبة ({qty}) أكبر من المتوفر فعلياً من "{self.name}" '
                f'({available}) — حدّث المخزون أولاً أو قلّل الكمية.'
            )
        self.available_qty = available - qty

    def add_stock(self, qty: float) -> None:
        self.available_qty = (self.available_qty or 0) + qty


class FeedRation(db.Model):
    """وصفة/تركيبة علف مسمّاة — نسبة كل مكوّن من إجمالي وزن الوصفة."""
    __tablename__ = "feed_rations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    purpose = db.Column(db.String(32))  # نمو / نفاس / حمل_متأخر / تسمين / صيانة
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)

    items = db.relationship("FeedRationItem", back_populates="ration", cascade="all, delete-orphan")


class FeedRationItem(db.Model):
    """مكوّن ضمن وصفة — نسبته المئوية من إجمالي وزن الوصفة."""
    __tablename__ = "feed_ration_items"

    id = db.Column(db.Integer, primary_key=True)
    ration_id = db.Column(db.Integer, db.ForeignKey("feed_rations.id"), nullable=False)
    ration = db.relationship("FeedRation", back_populates="items")
    feed_id = db.Column(db.Integer, db.ForeignKey("feeds.id"), nullable=False)
    feed = db.relationship("Feed")
    percent = db.Column(db.Float, nullable=False)  # % من إجمالي وزن الوصفة


class FeedBarnPlan(db.Model):
    """خطة تغذية حظيرة: وصفة معيّنة + كمية يومية لكل رأس."""
    __tablename__ = "feed_barn_plans"

    id = db.Column(db.Integer, primary_key=True)
    barn_id = db.Column(db.Integer, db.ForeignKey("barns.id"), nullable=False)
    barn = db.relationship("Barn")
    ration_id = db.Column(db.Integer, db.ForeignKey("feed_rations.id"), nullable=False)
    ration = db.relationship("FeedRation")

    daily_qty_per_animal_kg = db.Column(db.Float, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date)

    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)


class FeedMovement(db.Model):
    """حركة مخزون علف — وارد (شراء) أو صادر (توزيع فعلي على حظيرة/حيوان)."""
    __tablename__ = "feed_movements"

    id = db.Column(db.Integer, primary_key=True)
    feed_id = db.Column(db.Integer, db.ForeignKey("feeds.id"), nullable=False)
    feed = db.relationship("Feed")

    movement_type = db.Column(db.String(16), nullable=False)  # in / out
    quantity = db.Column(db.Float, nullable=False)
    before_qty = db.Column(db.Float)
    after_qty = db.Column(db.Float)

    barn_id = db.Column(db.Integer, db.ForeignKey("barns.id"), nullable=True)
    barn = db.relationship("Barn")
    animal_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=True)
    animal = db.relationship("Animal")

    note = db.Column(db.Text)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=_now)
