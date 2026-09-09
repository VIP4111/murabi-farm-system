from datetime import datetime, timezone
from flask_babel import lazy_gettext as _l
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class Finance(db.Model):
    """كل الحركات المالية: بيع، شراء، مصروف. لا تُحذف نهائياً أبداً — تُلغى
    (is_cancelled) عشان يضل سجل التدقيق كامل، بنفس مبدأ 'لا شيء يختفي بصمت'."""
    __tablename__ = "finance"

    # بند إصلاح (فحص عميق — طلبك: "ابدأ بند" على فجوة `Finance.category`
    # المخزَّنة عربي بحت وقت الكتابة بعشرات المواضع بالكود) — القيمة
    # الخام تبقى كما هي (صفر هجرة بيانات، صفر تغيير بمنطق التجميع
    # اللي يعتمد على القيمة الخام بالتقارير) — `display_category()`
    # يترجم بس وقت العرض. أي فئة حرة يكتبها المستخدم يدوياً بشاشة
    # "عملية جديدة" ترجع كما هي (fallback آمن، نفس أسلوب Role.display_label).
    CATEGORY_LABELS_AR = {
        "بيع رأس": _l("بيع رأس"),
        "شراء حيوان": _l("شراء حيوان"),
        "علاج مرض": _l("علاج مرض"),
        "زيارة بيطرية": _l("زيارة بيطرية"),
        "تحصين": _l("تحصين"),
        "صيانة معدات": _l("صيانة معدات"),
        "راتب موظف": _l("راتب موظف"),
        "هالك": _l("هالك"),
        "خسارة أصل": _l("خسارة أصل"),
        "فاتورة كهرباء": _l("فاتورة كهرباء"),
        "فاتورة ماء": _l("فاتورة ماء"),
        "بدون تصنيف": _l("بدون تصنيف"),
        # KIND_LABELS بـ stock_purchase_service.py (بند 259 — شراء مخزون
        # أعلاف/معدات/أدوية) يخزّن هذي القيم أيضاً بـ Finance.category.
        "أعلاف": _l("أعلاف"),
        "معدات": _l("معدات"),
        "أدوية": _l("أدوية"),
    }

    @classmethod
    def display_category_value(cls, category: str | None) -> str | None:
        if category is None:
            return None
        return str(cls.CATEGORY_LABELS_AR.get(category, category))

    def display_category(self) -> str | None:
        return self.display_category_value(self.category)

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, index=True)
    operation_type = db.Column(db.String(32), nullable=False)  # sale/purchase/expense
    category = db.Column(db.String(80))
    item = db.Column(db.String(160))
    description = db.Column(db.Text)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(32))

    related_animal_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=True, index=True)
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

    # الفاتورة (بند إضافي 75، 2026-07-31) — تفرقة مقصودة حسب اتجاه العملية:
    # بيع = المزرعة هي البائع فتُصدر فاتورة (invoice_number/invoice_issued_at،
    # تُبنى PDF عند أول إصدار وتبقى ثابتة بعدها)؛ شراء/مصروف = المزرعة هي
    # المشتري فترفق فاتورة المورّد الجاهزة إن وجدت (invoice_file_url) بدون
    # أي توليد. no_invoice علم صريح للبيع غير الرسمي (نقدي بدون فاتورة) —
    # مختلف عن "لسه ما صدرت الفاتورة".
    invoice_number = db.Column(db.String(40), unique=True, nullable=True)
    invoice_issued_at = db.Column(db.DateTime, nullable=True)
    invoice_file_url = db.Column(db.String(255), nullable=True)
    no_invoice = db.Column(db.Boolean, default=False, nullable=False)
    buyer_name = db.Column(db.String(120), nullable=True)
    buyer_phone = db.Column(db.String(30), nullable=True)
