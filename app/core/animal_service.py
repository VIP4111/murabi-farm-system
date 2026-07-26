"""
خدمة الحيوان — نقطة الدخول الموحّدة الوحيدة لإنشاء أي حيوان بالنظام.

هذا بالضبط الحل لمشكلة النظام القديم (أكثر من دالة saveAnimal/registerBirth...
كل وحدة تنسى شي المرة الثانية ما تنساه). أي كود بأي مكان بالنظام (شراء،
تسجيل ولادة، استيراد جماعي) يجب يمر من هالدالة ولا يسوي إدخال مباشر
لجدول Animal.
"""
from datetime import date
from app.extensions import db
from app.models.animal import Animal, AnimalSource
from app.models.animal_log import AnimalWeight, AnimalNote
from app.models.milk_record import MilkRecord


def generate_temp_animal_no(mother: Animal) -> str:
    """رقم تعريف مؤقت (بند إضافي، 2026-07-23) — لمولود يُسجَّل قبل ما توصله
    رقعة/رقم دائم. مبني على معرّف الأم بالضبط حسب قرارك: `TEMP-{رقم الأم}-N`
    حيث N يزيد لكل مولود إضافي لنفس الأم بنفس النمط، عشان ما يتكرر لو الأم
    ولدت أكثر من مرة أو توأم. يُستبدل لاحقاً بالرقم الدائم من شاشة تعديل
    الحيوان الجديدة (`/animals/<id>/edit`)."""
    prefix = f"TEMP-{mother.animal_no}-"
    existing = Animal.query.filter(Animal.animal_no.like(f"{prefix}%")).count()
    return f"{prefix}{existing + 1}"


def create_animal(
    *,
    animal_no: str | None,
    source: AnimalSource,
    gender: str,
    species: str = "sheep_goat",
    barn_id: int | None = None,
    mother_id: int | None = None,
    father_id: int | None = None,
    birth_date: date | None = None,
    purchase_date: date | None = None,
    entry_date: date | None = None,
    weight: float | None = None,
    price: float | None = None,
    purpose: str | None = None,
    color: str | None = None,
    name: str | None = None,
    image_url: str | None = None,
    breed: str | None = None,
) -> Animal:
    if source == AnimalSource.BIRTH and mother_id is None:
        raise ValueError("الحيوان المولود لازم يكون مربوط بأم (mother_id)")

    # معالجة السهو بالتواريخ (بند إضافي، 2026-07-23): كل مصدر له تاريخ
    # مرجعي لازم يُعبّى — لو نُسي بالواجهة (JS تجاوَزها المستخدم، أو طلب
    # مباشر للسيرفر)، يُفترض "اليوم" تلقائياً بدل ما يُحفظ الحيوان بدون
    # أي تاريخ مرجعي إطلاقاً (كان يكسر التقارير الزمنية وعمر الحيوان).
    if source == AnimalSource.BIRTH and birth_date is None:
        birth_date = date.today()
    if source == AnimalSource.PURCHASE and purchase_date is None:
        purchase_date = date.today()
    if source in (AnimalSource.GIFT, AnimalSource.OPENING_BALANCE) and entry_date is None:
        entry_date = date.today()

    if not animal_no:
        if source != AnimalSource.BIRTH or mother_id is None:
            raise ValueError("رقم الحيوان مطلوب — الرقم المؤقت التلقائي مقصور على المواليد المربوطة بأم")
        mother = Animal.query.get(mother_id)
        if not mother:
            raise ValueError("الأم غير موجودة")
        animal_no = generate_temp_animal_no(mother)

    animal = Animal(
        animal_no=animal_no,
        source=source,
        species=species,
        gender=gender,
        barn_id=barn_id,
        mother_id=mother_id,
        father_id=father_id,
        birth_date=birth_date,
        purchase_date=purchase_date,
        entry_date=entry_date,
        weight=weight,
        price=price,
        purpose=purpose,
        color=color,
        name=name,
        image_url=image_url,
        breed=breed or "عام/غير محدد",
        lifecycle_stage="source",
        status="active",
    )
    db.session.add(animal)
    db.session.commit()

    # تمييز الأثر المالي حسب المصدر (بند 18 بالمواصفة): الشراء فقط مصروف
    # فعلي يُسجَّل تلقائياً بجدول المالية — الهدية والرصيد الافتتاحي مو
    # مصروف جديد (حيوان موجود أصلاً أو دخل بدون مقابل مالي)، فما يُسجَّل
    # لهم أي حركة مالية. نفس مبدأ sell_animal() اللي يسجّل Finance تلقائياً
    # عند البيع — نقطة دخول موحّدة، بدون الاعتماد على تسجيل يدوي منفصل.
    if source == AnimalSource.PURCHASE and price:
        from app.models import Finance
        db.session.add(Finance(
            date=purchase_date or date.today(), operation_type="purchase", category="شراء حيوان",
            item=f"شراء {animal_no}", amount=price, related_animal_id=animal.id,
        ))
        db.session.commit()

    if species != "ostrich":
        # محرك دورة الإنتاج (CycleEvent/ProductionWorkflow) مبني بالكامل
        # على بيولوجيا المجترات — النعام ما يدخله إطلاقاً، فما نسجّل له
        # حتى حدث "source" الأساسي (بند 23).
        from app.core.cycle_engine import record_cycle_event
        record_cycle_event(animal, "source", source_type="Animal", source_id=animal.id,
                            event_date=birth_date or purchase_date or entry_date or date.today())

    if source == AnimalSource.BIRTH and mother_id and species != "ostrich":
        # خطة العزل التلقائية مبنية بالكامل على بيولوجيا المجترات (حظيرة
        # عزل، فحص دكتور، تحصين أم/مولود) — ما تنطبق على النعام، اللي
        # دورته (بيض→حضانة→فقس) مبنية بـapp/core/ostrich_service.py.
        mother = Animal.query.get(mother_id)
        if mother:
            record_cycle_event(mother, "birth", source_type="Animal", source_id=animal.id,
                                event_date=birth_date or date.today())

            from app.core.isolation_service import start_isolation_plan
            start_isolation_plan(mother=mother, newborn=animal, birth_date_=birth_date or date.today())

    return animal


def register_birth(*, mother: Animal, newborn_no: str | None = None, gender: str, weight: float | None = None) -> Animal:
    """تسجيل مولود جديد مرتبط بأمه — يُستخدم من زر "تم الولادة" بالمرحلة 4.
    `newborn_no` اختياري الآن — لو فاضي، `create_animal` يولّد رقماً مؤقتاً
    تلقائياً (بند إضافي، 2026-07-23)."""
    return create_animal(
        animal_no=newborn_no,
        source=AnimalSource.BIRTH,
        gender=gender,
        barn_id=mother.barn_id,
        mother_id=mother.id,
        birth_date=date.today(),
        weight=weight,
    )


def add_weight_record(*, animal: Animal, record_date: date, weight: float,
                       notes: str | None = None, recorded_by_id: int | None = None) -> AnimalWeight:
    """يسجّل قيد وزن جديد بسجل الحيوان. لو هذا القيد هو الأحدث تاريخياً (أو
    ما فيه قيود سابقة)، يُنسخ لحقل `Animal.weight` الحالي — نفس الحقل اللي
    تعتمد عليه بوابات محرك الدورة وحاسبة العلف، عشان تستمر تشتغل بدون أي
    تعديل عليها."""
    record = AnimalWeight(
        animal_id=animal.id, date=record_date, weight=weight,
        notes=notes, recorded_by_id=recorded_by_id,
    )
    db.session.add(record)
    db.session.flush()

    latest = (
        AnimalWeight.query.filter_by(animal_id=animal.id)
        .order_by(AnimalWeight.date.desc(), AnimalWeight.id.desc())
        .first()
    )
    if latest and latest.id == record.id:
        animal.weight = weight
        db.session.add(animal)

    db.session.commit()
    return record


def add_note(*, animal: Animal, note_date: date, note: str, created_by_id: int | None = None) -> AnimalNote:
    row = AnimalNote(animal_id=animal.id, date=note_date, note=note, created_by_id=created_by_id)
    db.session.add(row)
    db.session.commit()
    return row


def add_milk_record(*, animal: Animal, record_date: date, session: str, quantity_liters: float,
                     notes: str | None = None, recorded_by_id: int | None = None) -> MilkRecord:
    row = MilkRecord(
        animal_id=animal.id, date=record_date, session=session,
        quantity_liters=quantity_liters, notes=notes, recorded_by_id=recorded_by_id,
    )
    db.session.add(row)
    db.session.commit()
    return row
