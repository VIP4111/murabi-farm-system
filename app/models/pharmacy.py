from datetime import datetime, timezone
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
    MEDICINE_CLASSES = ["antiparasitic", "antibiotic", "vaccine", "supplement", "other"]
    MEDICINE_CLASS_LABELS_AR = {
        "antiparasitic": "مضاد طفيليات/ديدان",
        "antibiotic": "مضاد حيوي",
        "vaccine": "لقاح",
        "supplement": "مكمّل غذائي",
        "other": "أخرى",
    }

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(80))
    medicine_class = db.Column(db.String(20))

    # حظر نحاس سلالة النعيمي (بند إضافي 51) — نفس منطق `Feed.
    # contains_high_copper`، تُطبَّق على مضادات الديدان/المكمّلات
    # عالية النحاس المسجَّلة كدواء بدل علف.
    contains_high_copper = db.Column(db.Boolean, default=False, nullable=False)

    expiry_date = db.Column(db.Date)
    available_qty = db.Column(db.Float, default=0)
    unit = db.Column(db.String(32))
    withdrawal_days = db.Column(db.Integer, default=0, nullable=False)

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
            raise ValueError(
                f'الكمية المطلوبة ({qty}) أكبر من المتوفر فعلياً من "{self.name}" '
                f'({available}) — حدّث المخزون أولاً أو قلّل الكمية.'
            )
        self.available_qty = available - qty
