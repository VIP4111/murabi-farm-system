from datetime import datetime, timezone
from flask_babel import get_locale
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
    # بند إصلاح (فحص عميق — طلبك: "تأكد من باقي الشاشات ما فيهم نفس
    # المشكلة" بعد بلاغ أعراض المساعد التشخيصي) — نفس شاشة "طلب فحص
    # شامل لهذا الرأس" اللي طلبت ترتيبها كانت بنودها عربي بحت بلا أي
    # ترجمة، نفس نمط Symptom/DiseaseType بالضبط. `text` يبقى القيمة
    # المُرسَلة والمخزَّنة بالمهمة (بدون تغيير أي منطق قائم)، `text_en`
    # للعرض فقط لدكتور حسابه غير عربي.
    text_en = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=_now)

    def display_label(self) -> str:
        if self.text_en and str(get_locale()) != "ar":
            return self.text_en
        return self.text

    # بقيت `list[str]` عمداً (مو تعدد `(نص، ترجمة)`) — `PRESETS` باختبار
    # `test_checkup_ai_suggestion_302.py` (واقتراح الفحص بالذكاء
    # الاصطناعي) يستخدمها مباشرة كقائمة نصوص عربية للمطابقة مع رد
    # النموذج؛ الترجمة الإنجليزية منفصلة بـ`_DEFAULTS_EN` عشان ما تكسر
    # هذا الاستخدام الخارجي.
    _DEFAULTS = [
        "فحص الحرارة والنبض",
        "فحص الجلد والصوف (طفيليات خارجية)",
        "فحص العين والأنف",
        "فحص الخف/الحافر",
        "فحص الخراجات أو الكتل الظاهرة",
        "فحص الشهية والحالة العامة",
        "رفع تقرير حالة الرأس",
    ]
    _DEFAULTS_EN = {
        "فحص الحرارة والنبض": "Temperature & pulse check",
        "فحص الجلد والصوف (طفيليات خارجية)": "Skin & wool check (external parasites)",
        "فحص العين والأنف": "Eye & nose check",
        "فحص الخف/الحافر": "Hoof check",
        "فحص الخراجات أو الكتل الظاهرة": "Abscess / visible lump check",
        "فحص الشهية والحالة العامة": "Appetite & general condition check",
        "رفع تقرير حالة الرأس": "Submit head status report",
    }

    @classmethod
    def seed_defaults(cls) -> None:
        for order, text in enumerate(cls._DEFAULTS):
            text_en = cls._DEFAULTS_EN.get(text)
            existing = cls.query.filter_by(text=text).first()
            if not existing:
                db.session.add(cls(text=text, text_en=text_en, sort_order=order))
            elif not existing.text_en and text_en:
                existing.text_en = text_en
        db.session.commit()

    @classmethod
    def active_texts(cls) -> list[str]:
        return [p.text for p in cls.query.filter_by(is_active=True).order_by(cls.sort_order, cls.id).all()]

    @classmethod
    def label_map(cls) -> dict[str, str]:
        """قاموس {النص العربي: نص العرض المترجم} — يُستخدم بالقالب بدون
        كسر منطق `active_texts()`/`items` المُرسَل بالفورم (نفس القيمة
        العربية تبقى value/مفتاح، الترجمة للعرض فقط)."""
        return {p.text: p.display_label()
                for p in cls.query.filter_by(is_active=True).order_by(cls.sort_order, cls.id).all()}
