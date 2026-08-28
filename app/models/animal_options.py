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
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class SpeciesType(db.Model):
    __tablename__ = "species_types"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    label_ar = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, default=_now)

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


class AnimalColor(db.Model):
    __tablename__ = "animal_colors"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=_now)

    @classmethod
    def seed_defaults(cls) -> None:
        if cls.query.count() > 0:
            return
        for n in ("أبيض", "أسود", "أحمر", "بني", "رمادي", "مبرقش"):
            db.session.add(cls(name=n))
        db.session.commit()
