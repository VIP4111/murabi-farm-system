"""
خدمة الحيوان — نقطة الدخول الموحّدة الوحيدة لإنشاء أي حيوان بالنظام.

هذا بالضبط الحل لمشكلة النظام القديم (أكثر من دالة saveAnimal/registerBirth...
كل وحدة تنسى شي المرة الثانية ما تنساه). أي كود بأي مكان بالنظام (شراء،
تسجيل ولادة، استيراد جماعي) يجب يمر من هالدالة ولا يسوي إدخال مباشر
لجدول Animal.
"""
from datetime import date, timedelta
from app.extensions import db
from app.models.animal import Animal, AnimalSource
from app.models.animal_log import AnimalWeight, AnimalNote
from app.models.milk_record import MilkRecord


def _maybe_start_purchase_quarantine(animal: Animal) -> None:
    """رأس مشترى وُضع بحظيرة العزل (بند إضافي، 2026-07-28) يحصل تلقائياً
    على نفس مهمتي بداية دفعة الاستقبال (بند 52): رش وقائي وتحصين مبدئي —
    اختيار المالك لحظيرة العزل وقت التسجيل هو اللي يفعّل هذا، مو تلقائي
    بغض النظر عن الحظيرة المختارة (نفس مبدأ الاستقلالية اللي بُنيت عليه
    شاشة تسجيل الحيوان من الأساس)."""
    if not animal.barn_id:
        return
    from app.models import Barn
    from app.team import task_service

    barn = Barn.query.get(animal.barn_id)
    if not barn or barn.barn_type != "عزل":
        return

    task_service.create_suggested_task(
        title=f"🧴 رش وقائي — {animal.animal_no} (وافد جديد)",
        task_type="batch_spray", barn_id=animal.barn_id, animal_id=animal.id,
        due_date=date.today(), source_type="Animal", source_id=animal.id,
        notes="رش وقائي ضد الطفيليات الخارجية عند الاستقبال — قبل الاختلاط بباقي القطيع.",
    )
    task_service.create_suggested_task(
        title=f"💉 تحصين مبدئي إلزامي — {animal.animal_no} (وافد جديد)",
        task_type="batch_initial_vaccination", barn_id=animal.barn_id, animal_id=animal.id,
        due_date=date.today(), source_type="Animal", source_id=animal.id,
        notes="تحصين مبدئي عند الاستقبال حسب البروتوكول المتّبع بالمزرعة — إلزامي قبل خلط الرأس بالقطيع.",
    )


def _register_pregnancy_intake(animal: Animal, *, intake_date: date) -> None:
    """أنثى أُعلن عنها حامل وقت التسجيل (بند إضافي، 2026-07-28) — تُسجَّل
    كحمل غير مؤكَّد بعد (`Pregnancy.confirmed=False`، نفس جدول الحمل
    الموجود أصلاً بند 10 — بدون أي حقل جديد على Animal) بانتظار تأكيد
    الطبيب، وتتولّد مهمة "نقل لحظيرة الحوامل" مستحقة بنهاية فترة العزل.
    إنجاز هذي المهمة تحديداً هو اللي ينفّذ النقل الفعلي (نفس نمط
    `complete_task_via_treatment` — إجراء خاص يشغّله إنجاز نوع مهمة
    معيّن، انظر `task_service.complete_task`)."""
    from app.models import Pregnancy, FarmSettings
    from app.team import task_service

    db.session.add(Pregnancy(
        female_id=animal.id, date=intake_date, confirmed=False,
        notes="أُعلن عنها حامل وقت تسجيل الحيوان — بانتظار تأكيد الطبيب.",
    ))

    settings = FarmSettings.get()
    task_service.create_suggested_task(
        title=f"🤰 نقل {animal.animal_no} لحظيرة الحوامل بعد انتهاء العزل",
        task_type="move_to_pregnant_barn",
        animal_id=animal.id, barn_id=animal.barn_id,
        due_date=intake_date + timedelta(days=settings.isolation_days),
        source_type="PregnancyIntake", source_id=animal.id,
        notes="أُعلنت حامل وقت الشراء/الدخول — تأكد من العزل والفحص أولاً، ثم أنجز هذي المهمة لنقلها فعلياً لحظيرة الحوامل.",
    )
    db.session.commit()


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
    is_pregnant_at_intake: bool = False,
    invoice_file_url: str | None = None,
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

    # فحوصات سلامة إدخال (بند إضافي 187) — تمنع خطأ كتابة واضح قبل ما
    # يوصل قاعدة البيانات أصلاً (وزن/سعر غير منطقي، تاريخ بالمستقبل).
    from app.core import validation_service
    validation_service.validate_weight(weight, species=species)
    validation_service.validate_price(price, field_label="السعر")
    validation_service.validate_not_future_date(birth_date, field_label="تاريخ الولادة")
    validation_service.validate_not_future_date(purchase_date, field_label="تاريخ الشراء")
    validation_service.validate_not_future_date(entry_date, field_label="تاريخ الدخول")

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
            invoice_file_url=invoice_file_url,
        ))
        db.session.commit()

    if species == "sheep_goat":
        # محرك دورة الإنتاج (CycleEvent/ProductionWorkflow) مبني بالكامل
        # على بيولوجيا المجترات — أي فصيلة غير "حلال" (نعام أو أي فصيلة
        # جديدة تُضاف لاحقاً من شاشة الفصائل) ما تدخله إطلاقاً، فما نسجّل
        # لها حتى حدث "source" الأساسي (بند 23 + توسعة إضافة الفصائل
        # 2026-07-28: فصيلة جديدة تُعامَل بأمان كالنعام افتراضياً، لأنها
        # ما بُني لها نظام دورة مخصّص بعد).
        from app.core.cycle_engine import record_cycle_event
        record_cycle_event(animal, "source", source_type="Animal", source_id=animal.id,
                            event_date=birth_date or purchase_date or entry_date or date.today())

    if source == AnimalSource.PURCHASE and species == "sheep_goat":
        _maybe_start_purchase_quarantine(animal)

    if source == AnimalSource.BIRTH and mother_id and species == "sheep_goat":
        # خطة العزل التلقائية مبنية بالكامل على بيولوجيا المجترات (حظيرة
        # عزل، فحص دكتور، تحصين أم/مولود) — ما تنطبق على النعام، اللي
        # دورته (بيض→حضانة→فقس) مبنية بـapp/core/ostrich_service.py.
        mother = Animal.query.get(mother_id)
        if mother:
            record_cycle_event(mother, "birth", source_type="Animal", source_id=animal.id,
                                event_date=birth_date or date.today())

            from app.core.isolation_service import start_isolation_plan
            animal._isolation_barn_warning = start_isolation_plan(
                mother=mother, newborn=animal, birth_date_=birth_date or date.today())

    if gender == "أنثى" and is_pregnant_at_intake and source != AnimalSource.BIRTH:
        _register_pregnancy_intake(animal, intake_date=purchase_date or entry_date or date.today())

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
    from app.core import validation_service
    validation_service.validate_weight(weight, species=animal.species)
    validation_service.validate_not_future_date(record_date, field_label="تاريخ الوزن")

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
