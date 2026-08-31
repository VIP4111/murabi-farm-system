from datetime import datetime, timezone
from flask_babel import gettext as _
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class Pharmacy(db.Model):
    """مخزون الصيدلية — كل دواء له فترة سحب (withdrawal_days) تُستخدم تلقائياً
    عند تسجيل أي زيارة/علاج/تطعيم يستخدم هذا الدواء (انظر health.py)."""
    __tablename__ = "pharmacy"

    # فئة الدواء (بند إضافي 50) — قائمة ثابتة مغلقة، منفصلة عمداً عن
    # `category` النصي الحر (المستخدم أصلاً لاقتراح البدائل بنفس
    # التصنيف، بند 48) — هذي تحديداً عشان حارس منع تكرار جرعة الطفيليات
    # خلال 30 يوماً يحتاج تمييزاً موثوقاً لا يعتمد على دقة كتابة الطبيب.
    MEDICINE_CLASSES = ["antiparasitic", "antibiotic", "vaccine", "supplement", "topical_disinfectant", "other"]
    MEDICINE_CLASS_LABELS_AR = {
        "antiparasitic": "مضاد طفيليات/ديدان",
        "antibiotic": "مضاد حيوي",
        "vaccine": "لقاح/تحصين",
        "supplement": "فيتامينات ومكمّلات",
        "topical_disinfectant": "مطهرات وعلاجات موضعية",
        "other": "أخرى",
    }
    # ترجمة إنجليزية (بند إضافي، طلبك الصريح: "بنسبه للخيارات نفس
    # الحكايه ابيها عربي انجليزي") — تُعرض جنب العربي بقائمة "فئة الدواء"
    # المنسدلة، بنفس مبدأ PERMISSIONS_EN/MEDICINE_CLASS_GUIDE_EN.
    MEDICINE_CLASS_LABELS_EN = {
        "antiparasitic": "Antiparasitic / dewormer",
        "antibiotic": "Antibiotic",
        "vaccine": "Vaccine / immunization",
        "supplement": "Vitamins and supplements",
        "topical_disinfectant": "Disinfectants and topical treatments",
        "other": "Other",
    }

    # ظروف التخزين (بند إضافي 61، 2026-07-28) — وصفي بس، ما يشغّل أي منطق
    # آلي (لا تنبيه ولا حظر) — يظهر بفورم الدواء عشان العامل يعرف وين
    # يحفظ الدواء فعلياً.
    STORAGE_CONDITIONS = ["refrigerated", "dry_dark", "frozen"]
    STORAGE_CONDITION_LABELS_AR = {
        "refrigerated": "مبرّد (2-8° مئوية)",
        "dry_dark": "مكان جاف ومظلم (أقل من 25° مئوية)",
        "frozen": "مجمَّد",
    }
    STORAGE_CONDITION_LABELS_EN = {
        "refrigerated": "Refrigerated (2-8°C)",
        "dry_dark": "Dry, dark place (under 25°C)",
        "frozen": "Frozen",
    }

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(80))
    medicine_class = db.Column(db.String(20))

    # وسم معلوماتي: هل يحتوي هذا الدواء/المكمّل نحاساً مرتفعاً (بند إضافي 51).
    contains_high_copper = db.Column(db.Boolean, default=False, nullable=False)

    expiry_date = db.Column(db.Date)
    available_qty = db.Column(db.Float, default=0)
    unit = db.Column(db.String(32))
    # فترة سحب اللحم/الذبح — الاسم القديم `withdrawal_days` أُبقي كما هو
    # (بدون تغيير المعنى للبيانات الموجودة أصلاً) عشان صفر خطر ترحيل؛
    # فقط وضّحنا بالتعليق إنه تحديداً للحم لا الحليب.
    withdrawal_days = db.Column(db.Integer, default=0, nullable=False)
    # فترة سحب الحليب (بند إضافي، 2026-08-30) — طلبك الصريح: "عندي
    # تحريم رضاعة الحليب وتحريم فترة الذبح [منفصلين]". قبل هذا البند
    # كان فيه حقل واحد بس يُستخدم لمنع البيع والحليب مع بعض بنفس المدة
    # — غير دقيق طبياً، لأن كثير أدوية بيطرية فترة سحب الحليب تختلف
    # (غالباً أقصر) عن فترة سحب اللحم. صفر لو الدواء ما له فترة سحب
    # حليب مستقلة (يبقى السلوك القديم كما هو لو تُرك 0).
    withdrawal_days_milk = db.Column(db.Integer, default=0, nullable=False)

    # الحد الأدنى للتنبيه (بند إضافي، 2026-07-24) — نفس حقل Feed.min_stock_qty
    # بالضبط. أي دواء وصل مخزونه له أو أقل يظهر بقائمة "نواقص الصيدلية"
    # الجديدة (`/health/pharmacy/shortages`) تلقائياً.
    min_stock_qty = db.Column(db.Float, default=0)

    # سعر الوحدة (بند إضافي، 2026-07-23) — أساس حساب تكلفة العلاج تلقائياً
    # (الكمية المستخدمة × سعر الوحدة) بدل إدخالها يدوياً بكل زيارة/مرض/
    # تطعيم. راجع app/health/health_service.py:_computed_cost.
    unit_price = db.Column(db.Float)

    # مرجع سريع للاستخدام (بند إضافي، 2026-07-23) — يُدخله من يدير مخزون
    # الصيدلية مرة وحدة لكل دواء، ويظهر بعدها بالقوائم المنسدلة بشاشات
    # الزيارة/المرض/التطعيم لتسريع الإدخال. **مرجع وصفي بس، مو حساب أو
    # توصية جرعة تلقائية** — النظام ما يحسب ولا يقترح أي جرعة، بس يعيد
    # عرض اللي كتبه الدكتور بنفسه (قاعدة "المساعد قرار مو طبيب" — بند 13).
    usage_method = db.Column(db.String(32))  # حقن عضل/حقن وريدي/حقن تحت الجلد/فموي/موضعي/رذاذ
    standard_dosage_note = db.Column(db.Text)

    # مدة الحماية باللقاح بالأيام (بند إضافي، 2026-07-28) — يُستخدم فقط
    # لجدولة "الموعد القادم" تلقائياً بشاشة التحصين الجماعي (تاريخ
    # التحصين + هذي المدة). ما له علاقة بحساب جرعة — مجرد مدة زمنية.
    protection_days = db.Column(db.Integer, nullable=True)

    # الجرعة الافتراضية للرأس بالمل (بند إضافي 61، 2026-07-28) — رقم واحد
    # ثابت يكتبه الدكتور، منفصل عن جدول "الجرعة حسب العمر" (`PharmacyDoseRule`)
    # — يُستخدم بس كقيمة احتياطية تُعرض بشاشة التحصين الجماعي لو عمر الرأس
    # ما طابق أي نطاق بالجدول، وتبقى قابلة للتعديل اليدوي دائماً.
    default_dose_ml = db.Column(db.Float, nullable=True)

    # ظروف التخزين (بند إضافي 61) — انظر STORAGE_CONDITIONS بالأعلى.
    storage_condition = db.Column(db.String(20), nullable=True)

    notes = db.Column(db.Text)
    status = db.Column(db.String(32), default="active", nullable=False)
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)

    def deduct_stock(self, qty: float) -> None:
        """سحب سالب ممنوع (بند إضافي، 2026-07-23) — كان يُقصّ عند الصفر
        بصمت (`max(0, ...)`)، فيسجّل استخدام دواء بكمية أكبر من المتوفر
        فعلياً بدون أي تنبيه، فيكسر دقة المخزون والتكلفة المحسوبة تلقائياً
        منه. صار يرفض العملية كاملة بدل القصّ الصامت."""
        available = self.available_qty or 0
        if qty > available:
            raise ValueError(_(
                'الكمية المطلوبة (%(qty)s) أكبر من المتوفر فعلياً من "%(name)s" '
                '(%(available)s) — حدّث المخزون أولاً أو قلّل الكمية.',
                qty=qty, name=self.name, available=available,
            ))
        self.available_qty = available - qty
        self._consume_batches_fifo(qty)

    def add_stock(self, qty: float) -> None:
        self.available_qty = (self.available_qty or 0) + qty

    def _consume_batches_fifo(self, qty: float) -> None:
        """بند إضافي 96 — خصم الكمية من أقدم دفعة شراء أولاً (FIFO)، عشان
        الدواء اللي دخل أول يخرج أول ويقارب تاريخ انتهائه ينخصم قبل غيره.
        هذي نقطة الاختيار المركزية الوحيدة (`deduct_stock` نفسها لها
        نداء واحد فقط بكل المشروع، من `health_service.py`)، فالتعديل هنا
        يغطي كل مسارات الاستخدام بدون أي تعديل بمكان ثاني. لو الدفعات
        المسجَّلة (`remaining_qty`) مجموعها أقل من الكمية المطلوبة — ينقص
        اللي متوفر منها بس ويتجاهل الباقي بصمت، لأن `available_qty` يبقى
        المرجع الرسمي دائماً (دواء أُضيف مخزونه يدوياً قبل بدء استخدام
        الدفعات، مثلاً، ما له دفعة يتسجّل منها)."""
        remaining_to_deduct = qty
        batches = sorted(
            [b for b in self.batches if (b.remaining_qty or 0) > 0],
            key=lambda b: b.purchase_date,
        )
        for batch in batches:
            if remaining_to_deduct <= 0:
                break
            take = min(batch.remaining_qty, remaining_to_deduct)
            batch.remaining_qty -= take
            remaining_to_deduct -= take


class PharmacyBatch(db.Model):
    """دفعة شراء دواء بتاريخها الخاص (بند إضافي 96) — قبل هذا، كل شراء
    جديد كان يُضاف بصمت لرقم `Pharmacy.available_qty` الإجمالي بدون أي
    أثر لتاريخ الشراء أو تاريخ انتهاء تلك الدفعة تحديداً (`expiry_date`
    كان حقلاً واحداً للدواء كله، مو لكل عملية شراء منفصلة)."""
    __tablename__ = "pharmacy_batches"

    id = db.Column(db.Integer, primary_key=True)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey("pharmacy.id"), nullable=False)
    pharmacy = db.relationship("Pharmacy", backref=db.backref("batches", cascade="all, delete-orphan"))

    purchase_date = db.Column(db.Date, nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    # الكمية المتبقية من هذي الدفعة تحديداً — تنخصم تدريجياً (FIFO) عند
    # أي استخدام فعلي، منفصلة عن `quantity` (الكمية الأصلية وقت الشراء،
    # تبقى ثابتة كسجل تاريخي).
    remaining_qty = db.Column(db.Float, nullable=False)
    expiry_date = db.Column(db.Date, nullable=True)
    unit_price = db.Column(db.Float, nullable=True)

    notes = db.Column(db.Text)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=_now)
