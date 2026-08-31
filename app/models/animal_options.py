"""
قوائم مرجعية قابلة للتوسّع لتسجيل الحيوان (بند إضافي، 2026-07-28) — نفس
فلسفة `DiseaseType` بالضبط: جدول صغير + زر "+ إضافة" (`animals.manage`)
بدل قائمة Python ثابتة (`Animal.BREEDS` القديمة) أو نص حر بدون اقتراحات.

`SpeciesType.code` **يبقى قيمة برمجية ثابتة يقرأها الكود** (`sheep_goat`/
`ostrich`/...) — إضافة فصيلة جديدة من الواجهة ما تبني نظاماً موازياً
تلقائياً (زي النعام)، فأي فصيلة غير "حلال" (`sheep_goat`) **ما تدخل محرك
دورة الإنتاج افتراضياً** لحمايتها من خلل بيانات حقيقي (راجع تحذير قدّمناه
للمستخدم قبل البناء، وافق عليه صراحة). `Breed`/`AnimalColor` أبسط —
`Animal.breed`/`Animal.color` يبقيان نص حر بالجدول (بدون FK) تماماً مثل
`Disease.disease_name`؛ هذي الجداول مرجع اقتراحات فقط.
"""
from datetime import datetime, timezone
from flask_babel import lazy_gettext as _l, get_locale
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


# بند إضافي (2026-08-31) — طلبك المباشر بعد صورة شاشة تسجيل حيوان:
# خيارَي الفصيلة الافتراضيَين ("حلال (ضأن/ماعز)"/"نعام") كانا يطلعان
# عربياً خاماً بقائمة اختيار الفصيلة حتى لحساب إنجليزي بالكامل. `code`
# قيمة ثابتة معروفة (`sheep_goat`/`ostrich`)، فترجمتها ممكنة بأمان —
# عكس أي فصيلة يضيفها المستخدم لاحقاً بزر "+" (نص حر، مو نص نظام،
# نفس مبدأ عدم ترجمة أسماء الحيوانات/الحظائر المخصَّصة).
_KNOWN_SPECIES_LABELS = {
    "sheep_goat": _l("حلال (ضأن/ماعز)"),
    "ostrich": _l("نعام"),
}


class SpeciesType(db.Model):
    __tablename__ = "species_types"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    label_ar = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, default=_now)

    def display_label(self) -> str:
        """اسم الفصيلة المترجَم لو كان أحد الاثنين الافتراضيَين
        المعروفَين، وإلا الاسم العربي الأصلي كما كتبه المستخدم (فصيلة
        مخصَّصة أضافها بنفسه — بيانات حرة، مو نص نظام)."""
        known = _KNOWN_SPECIES_LABELS.get(self.code)
        return str(known) if known is not None else self.label_ar

    @classmethod
    def seed_defaults(cls) -> None:
        if cls.query.count() > 0:
            return
        db.session.add(cls(code="sheep_goat", label_ar="حلال (ضأن/ماعز)"))
        db.session.add(cls(code="ostrich", label_ar="نعام"))
        db.session.commit()


class Breed(db.Model):
    __tablename__ = "breeds"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    # بند إضافي (2026-08-31) — طلبك المباشر بعد إصلاح قائمة الفصيلة:
    # اسم إنجليزي اختياري لكل سلالة، نفس نمط `Barn.barn_name_en`
    # بالضبط. `name` نص حر يضيفه المستخدم بزر "+" — عكس `SpeciesType`
    # ما فيه "قيم افتراضية معروفة" بكود ثابت، فكل سلالة (حتى المزروعة
    # افتراضياً بـ`seed_defaults`) تُعامَل نفس معاملة أي إدخال مخصَّص:
    # تترجم فقط لو المستخدم كتب لها اسماً إنجليزياً بنفسه.
    name_en = db.Column(db.String(60), nullable=True)
    # ملاحظات رعاية خاصة بالسلالة (بند إضافي 174) — يكتبها صاحب
    # الحلال أو الطبيب بأنفسهم بناءً على خبرتهم الفعلية بهذي السلالة
    # بمنطقتهم/مناخهم — النظام عمداً **ما يخترع** أي معلومة سلالة/مناخ
    # محدَّدة (دقة زائفة خطرة)؛ هذا حقل فاضي بالبداية دائماً، قيمته من
    # معرفة المستخدم الحقيقية فقط.
    care_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)

    @classmethod
    def seed_defaults(cls) -> None:
        """بند إضافي 289 — صارت idempotent لكل اسم على حدة (مو بس أول
        تشغيل للنظام كامل) عشان مزرعة شغّالة أصلاً (عندها سلالات
        مسجَّلة من قبل) تقدر تلتقط سلالة افتراضية جديدة أُضيفت بالكود
        لاحقاً (زي "ماعز" هنا) بمجرّد إعادة تشغيل `flask seed` — بدون
        هذا التغيير، الحارس القديم (`count() > 0`) كان يوقف أي إضافة
        مستقبلية بمجرد وجود سلالة واحدة، حتى لو كانت غير هذي بالاسم."""
        for n in ("نعيمي", "ماعز", "عام/غير محدد"):
            if not cls.query.filter_by(name=n).first():
                db.session.add(cls(name=n))
        db.session.commit()

    def display_label(self) -> str:
        """اسم السلالة بالإنجليزي لو مضبوط والمستخدم لغته غير عربية،
        وإلا الاسم العربي كما هو (سلوك قديم محفوظ بدون كسر)."""
        if self.name_en and str(get_locale()) != "ar":
            return self.name_en
        return self.name


class AnimalColor(db.Model):
    __tablename__ = "animal_colors"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    name_en = db.Column(db.String(60), nullable=True)
    created_at = db.Column(db.DateTime, default=_now)

    def display_label(self) -> str:
        if self.name_en and str(get_locale()) != "ar":
            return self.name_en
        return self.name

    @classmethod
    def seed_defaults(cls) -> None:
        """idempotent لكل اسم على حدة (نفس تصحيح `Breed.seed_defaults`
        أعلاه، بند إضافي 289) — عشان مزرعة شغّالة أصلاً تلتقط أي لون
        افتراضي جديد أُضيف بالكود لاحقاً (زي "أصفر" هنا، طلبك الصريح)
        بمجرّد إعادة تشغيل `flask seed`، بدل ما يوقفها الحارس القديم
        (`count() > 0`) لمجرد وجود لون واحد من قبل."""
        for n in ("أبيض", "أسود", "أحمر", "بني", "رمادي", "أصفر", "مبرقش"):
            if not cls.query.filter_by(name=n).first():
                db.session.add(cls(name=n))
        db.session.commit()
