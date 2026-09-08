from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class CheckupItemPreset(db.Model):
    """بند فحص جاهز يظهر بقائمة "طلب فحص شامل لهذا الرأس" (بند إضافي —
    طلبك الصريح: "صاحب الحلال يستطيع الحذف والاستبدال والاضافة"). كانت
    قائمة ثابتة بالكود (`ANIMAL_CHECKUP_ITEM_PRESETS`) — صارت مُدارة من
    الإعدادات، صاحب الحلال يضيف/يعدّل/يحذف بندوده الخاصة بلا حاجة
    تعديل برمجي. البذور الافتراضية (نفس السبعة بنود القديمة بالضبط)
    تُزرع مرة وحدة (`seed_defaults`، نفس نمط `AnimalColor`) — صفر كسر
    لأي مزرعة شغّالة أصلاً."""
    __tablename__ = "checkup_item_presets"

    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=_now)

    _DEFAULTS = [
        "فحص الحرارة والنبض",
        "فحص الجلد والصوف (طفيليات خارجية)",
        "فحص العين والأنف",
        "فحص الخف/الحافر",
        "فحص الخراجات أو الكتل الظاهرة",
        "فحص الشهية والحالة العامة",
        "رفع تقرير حالة الرأس",
    ]

    @classmethod
    def seed_defaults(cls) -> None:
        for order, text in enumerate(cls._DEFAULTS):
            if not cls.query.filter_by(text=text).first():
                db.session.add(cls(text=text, sort_order=order))
        db.session.commit()

    @classmethod
    def active_texts(cls) -> list[str]:
        return [p.text for p in cls.query.filter_by(is_active=True).order_by(cls.sort_order, cls.id).all()]
