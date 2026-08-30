"""
قائمة "طريقة الاستخدام" القابلة للتوسّع (بند إضافي 61، 2026-07-28) — نفس
فلسفة `DiseaseType`/`Breed`/`AnimalColor` بالضبط: جدول صغير + زر "+ إضافة"
(`medical_options.manage`) بدل قائمة Python ثابتة كانت مكتوبة مباشرة
بالقالب. `Pharmacy.usage_method` يبقى نص حر بالجدول (بدون FK) — هذا
الجدول مرجع اقتراحات فقط، تماماً مثل `Breed`/`AnimalColor`.
"""
from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class UsageRoute(db.Model):
    __tablename__ = "usage_routes"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=_now)

    @classmethod
    def seed_defaults(cls) -> None:
        if cls.query.count() > 0:
            return
        for n in ("حقن عضل", "حقن وريدي", "حقن تحت الجلد", "فموي", "موضعي", "رذاذ/استنشاق", "أخرى"):
            db.session.add(cls(name=n))
        db.session.commit()


# ترجمة إنجليزية للأسماء السبعة المبذورة افتراضياً بس (بند إضافي، طلبك
# الصريح: "بنسبه للخيارات نفس الحكايه ابيها عربي انجليزي") — أي اسم
# طريقة استخدام يضيفه صاحب الحلال لاحقاً بنفسه (زر "+ إضافة") نص حر
# بدون كود ثابت، فما له ترجمة تلقائية — نفس القيد المنطقي المطبَّق على
# DiseaseType/Breed/AnimalColor.
USAGE_ROUTE_LABELS_EN = {
    "حقن عضل": "Intramuscular injection",
    "حقن وريدي": "Intravenous injection",
    "حقن تحت الجلد": "Subcutaneous injection",
    "فموي": "Oral",
    "موضعي": "Topical",
    "رذاذ/استنشاق": "Spray / inhalation",
    "أخرى": "Other",
}
