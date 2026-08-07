import enum
from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class AnimalSource(enum.Enum):
    PURCHASE = "purchase"
    BIRTH = "birth"
    GIFT = "gift"  # هدية/دعم عيني — أصل وليس مصروف شراء
    OPENING_BALANCE = "opening_balance"  # رصيد افتتاحي — رأس مال أول لا مصروف جديد


class Animal(db.Model):
    """
    نقطة دخول واحدة موحّدة: أي حيوان (مشترى أو مولود بالمزرعة) يُنشأ عبر نفس
    هذا الجدول ونفس الخدمة (انظر app/core/animal_service.py). الفرق الوحيد
    هو حقل `source` وربط `mother_id` لو كان مولوداً. هذا يمنع بالضبط مشكلة
    "نقاط الدخول المتعددة" اللي كانت بالنظام القديم.
    """
    __tablename__ = "animals"

    id = db.Column(db.Integer, primary_key=True)
    animal_no = db.Column(db.String(32), unique=True, nullable=False)

    # الفصيلة (بند 23) — sheep_goat هو الافتراضي (كل الحيوانات الحالية)،
    # ostrich فصيلة جديدة تشارك نفس الجدول والوحدات العامة (حظائر، صحة،
    # مالية، أوزان) لكن ما تدخل محرك دورة الإنتاج (تقريع/حمل/فطام) لأنه
    # مبني بالكامل على بيولوجيا المجترات — انظر app/ostrich/ للتفقيس.
    species = db.Column(db.String(20), default="sheep_goat", nullable=False)

    # السلالة (بند إضافي 51) — قائمة مختصرة قابلة للتوسعة، مو حقلاً نصياً
    # حراً، عشان يصير أساساً موثوقاً لقواعد آلية خاصة بسلالة معيّنة.
    BREEDS = ["نعيمي", "عام/غير محدد", "أخرى"]
    breed = db.Column(db.String(40), default="عام/غير محدد")

    source = db.Column(db.Enum(AnimalSource), nullable=False)
    mother_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=True)
    mother = db.relationship("Animal", remote_side=[id], foreign_keys=[mother_id])
    father_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=True)
    father = db.relationship("Animal", remote_side=[id], foreign_keys=[father_id])

    gender = db.Column(db.String(16))
    color = db.Column(db.String(60))
    name = db.Column(db.String(120))
    image_url = db.Column(db.String(255))

    birth_date = db.Column(db.Date)
    purchase_date = db.Column(db.Date)
    # تاريخ دخول المزرعة فعلياً — قد يختلف عن تاريخ الشراء، ويُستخدم أيضاً
    # كتاريخ مرجعي للهدية/الرصيد الافتتاحي (ما إلهم "تاريخ شراء").
    entry_date = db.Column(db.Date)
    # تاريخ دخول العزل الحالي (بند إضافي 148) — يُضبط عند "دخول عزل" ويُصفَّر
    # عند "خروج من العزل"، بمعزل تماماً عن أي نقل حظيرة عادي (نقل بين
    # حظيرتي عزل مختلفتين ما يلمس هذا الحقل أبداً — عداد الأيام يستمر).
    isolation_started_at = db.Column(db.Date)
    weight = db.Column(db.Float)
    price = db.Column(db.Float)

    # الغرض من تربية الحيوان — يحدّد "المسار" اللي يمشي عليه بمحرك دورة
    # الإنتاج (انظر app/core/cycle_engine.py). تربية/تسمين/بيع سريع.
    purpose = db.Column(db.String(32))

    barn_id = db.Column(db.Integer, db.ForeignKey("barns.id"))
    barn = db.relationship("Barn", back_populates="animals")

    # مسار استقبال دفعة جديدة (بند إضافي 52) — batch_id فارغ لأي حيوان
    # ما دخل عبر مسار دفعة (شراء فردي، مولود بالمزرعة...). batch_hold_
    # reason لو معبّى يستثني الرأس من التقدّم الجماعي التالي لدفعته
    # (عزل/استبعاد فردي لرأس مشتبه بها، قرارك الصريح) — يبقى بمرحلته
    # الحالية لحين "تحرير" الاستبعاد أو تقدّمه فردياً لاحقاً.
    batch_id = db.Column(db.Integer, db.ForeignKey("animal_batches.id"), nullable=True)
    batch = db.relationship("AnimalBatch", back_populates="animals")
    batch_hold_reason = db.Column(db.Text, nullable=True)

    # مكان محجوز لمحرك دورة الإنتاج (يُبنى بالمرحلة 3) — الحقل موجود من الآن
    # عشان ما نحتاج نعدّل الجدول لاحقاً.
    lifecycle_stage = db.Column(db.String(32), default="source", nullable=False)

    # علامات بيع يدوية للأنثى (بند 19 — محرك البيع الذكي) — ما تُحسب من
    # بيانات موجودة، لازم ملاحظة فعلية من المالك/الدكتور.
    refuses_nursing = db.Column(db.Boolean)
    udder_damaged = db.Column(db.Boolean)

    status = db.Column(db.String(32), default="active", nullable=False)  # active/sold/dead
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)

    def __repr__(self):
        return f"<Animal {self.animal_no}>"
