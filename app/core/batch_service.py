"""
مسار استقبال دفعة جديدة بمراحل (بند إضافي 52، جزء 2) — 3 مراحل:
1) حجر صحي وأوليات (`create_batch`) — تسجيل كل رؤوس الدفعة عبر
   `animal_service.create_animal` (نقطة الدخول الموحّدة، بند 7)، نقلها
   لحظيرة العزل، ومهمتا رش وتحصين مبدئي لكل رأس.
2) ترقيم وفحص سلامة فردي (`advance_batch_stage`) — تقدّم جماعي بضغطة
   زر واحدة (قرارك الصريح).
3) توزيع على حظائر دائمة + ربط عليقة (`distribute_batch`) — يحتاج
   تحديد حظيرة فعلية لكل رأس (قرار حقيقي، مو تلقائياً بالكامل).

أي رأس عليها `batch_hold_reason` (استبعاد/عزل فردي، `hold_animal`)
تُستثنى تلقائياً من أي تقدّم جماعي، وتبقى بمرحلتها الحالية لحين تحرير
الاستبعاد ولحاقها فردياً عبر `advance_single_animal`.
"""
from datetime import date
from app.extensions import db
from app.models import AnimalBatch, Animal, Barn, AuditLog
from app.models.animal import AnimalSource
from app.core.animal_service import create_animal
from app.team import task_service


def generate_batch_no(arrival_date: date) -> str:
    prefix = f"BATCH-{arrival_date.strftime('%Y%m%d')}-"
    existing = AnimalBatch.query.filter(AnimalBatch.batch_no.like(f"{prefix}%")).count()
    return f"{prefix}{existing + 1}"


def _quarantine_barn_id() -> int | None:
    barn = Barn.query.filter_by(barn_type="عزل").order_by(Barn.id).first()
    return barn.id if barn else None


def create_batch(*, source: str, arrival_date: date, notes: str | None,
                  actor_user_id: int, entries: list[dict]) -> AnimalBatch:
    if not entries:
        raise ValueError("لازم رأس واحدة على الأقل بالدفعة.")
    if source not in AnimalBatch.SOURCES:
        raise ValueError(f'مصدر غير معروف: "{source}"')
    # بند إضافي 286 — طلبك الصريح: نفس قيد اللون الإلزامي بشاشتي "+
    # حيوان جديد" و"الاستقبال الجماعي" (بند 285)، مطبَّق هنا أيضاً —
    # قبل هذا البند كل رأس بهذي الشاشة كان يُسجَّل بلون فاضي دائماً
    # لأن الفورم نفسه ما فيه حقل لون إطلاقاً.
    for idx, entry in enumerate(entries, start=1):
        if not entry.get("color"):
            label = entry.get("animal_no") or f"صف رقم {idx}"
            raise ValueError(f"{label}: لازم تحدد اللون.")

    batch = AnimalBatch(
        batch_no=generate_batch_no(arrival_date), source=source,
        arrival_date=arrival_date, notes=notes, created_by_id=actor_user_id,
    )
    db.session.add(batch)
    db.session.flush()

    barn_id = _quarantine_barn_id()
    animal_source = AnimalSource.PURCHASE if source == "purchase" else AnimalSource.GIFT

    from app.models import FarmSettings
    fs = FarmSettings.get()

    for entry in entries:
        animal = create_animal(
            animal_no=entry.get("animal_no") or None,
            source=animal_source, gender=entry["gender"], barn_id=barn_id,
            weight=entry.get("weight"), price=entry.get("price"),
            purpose=entry.get("purpose"), color=entry.get("color"), name=entry.get("name"),
            breed=entry.get("breed"),
            purchase_date=arrival_date if animal_source == AnimalSource.PURCHASE else None,
            entry_date=arrival_date if animal_source == AnimalSource.GIFT else None,
        )
        animal.batch_id = batch.id
        db.session.add(animal)

        # ربط بصنف صيدلية فعلي (بند إضافي 286، امتداد لبند 283) — نفس
        # آلية `animal_service._maybe_start_purchase_quarantine` بالضبط،
        # مطبَّقة هنا كمان بما إن هذي الشاشة عندها مسار توليد مهام
        # منفصل تماماً (ما كان يستفيد من إصلاح بند 283 أصلاً).
        spray_task = task_service.create_suggested_task(
            title=f"🧴 رش وقائي — {animal.animal_no} (دفعة {batch.batch_no})",
            task_type="batch_spray", barn_id=barn_id, animal_id=animal.id,
            due_date=arrival_date, source_type="AnimalBatch", source_id=batch.id,
            notes="رش وقائي ضد الطفيليات الخارجية عند الاستقبال — قبل الاختلاط بباقي القطيع.",
        )
        if fs.default_intake_spray_pharmacy_id:
            spray = fs.default_intake_spray_pharmacy
            spray_task.planned_pharmacy_id = spray.id
            spray_task.planned_quantity = spray.default_dose_ml
            spray_task.planned_treatment_kind = "vet_visit"
            spray_task.notes += f"\nالدواء المقترح: {spray.name} (يفحص المخزون تلقائياً عند تأكيد التنفيذ)."

        vaccination_task = task_service.create_suggested_task(
            title=f"💉 تحصين مبدئي — {animal.animal_no} (دفعة {batch.batch_no})",
            task_type="batch_initial_vaccination", barn_id=barn_id, animal_id=animal.id,
            due_date=arrival_date, source_type="AnimalBatch", source_id=batch.id,
            notes="تحصين مبدئي عند الاستقبال حسب البروتوكول المتّبع بالمزرعة.",
        )
        if fs.default_intake_vaccine_pharmacy_id:
            vaccine = fs.default_intake_vaccine_pharmacy
            vaccination_task.planned_pharmacy_id = vaccine.id
            vaccination_task.planned_quantity = vaccine.default_dose_ml
            vaccination_task.planned_treatment_kind = "vaccination"
            vaccination_task.notes += f"\nاللقاح المقترح: {vaccine.name} (يفحص المخزون تلقائياً عند تأكيد التنفيذ)."

    db.session.add(AuditLog(actor_user_id=actor_user_id, action="batch.create",
                             entity_type="AnimalBatch", entity_id=batch.id,
                             details=f"{len(entries)} رأس، مصدر {source}"))
    db.session.commit()
    return batch


def _active_members(batch: AnimalBatch) -> list[Animal]:
    return [a for a in batch.animals if a.status == "active"]


def _eligible_members(batch: AnimalBatch) -> list[Animal]:
    """رؤوس الدفعة المؤهَّلة للتقدّم الجماعي — نشطة وغير مستبعدة فردياً."""
    return [a for a in _active_members(batch) if not a.batch_hold_reason]


def _apply_stage2_tagging(batch: AnimalBatch, animal: Animal):
    return task_service.create_suggested_task(
        title=f"🏷️ ترقيم وفحص سلامة فردي — {animal.animal_no} (دفعة {batch.batch_no})",
        task_type="batch_tagging_check", barn_id=animal.barn_id, animal_id=animal.id,
        due_date=date.today(), source_type="AnimalBatch", source_id=batch.id,
        notes="توليد رقم تسلسلي/شريحة دائم + تسجيل فردي + فحص سلامة قبل التوزيع على الحظائر الدائمة.",
    )


def _apply_stage3_distribution(batch: AnimalBatch, animal: Animal, barn_id: int):
    animal.barn_id = barn_id
    db.session.add(animal)
    return task_service.create_suggested_task(
        title=f"🌾 ربط عليقة الحظيرة — {animal.animal_no} (دفعة {batch.batch_no})",
        task_type="batch_feed_link", barn_id=barn_id, animal_id=animal.id,
        due_date=date.today(), source_type="AnimalBatch", source_id=batch.id,
        notes="تأكد من ربط هذي الحظيرة بخطة تغذية مناسبة (FeedBarnPlan) لو ما فيه خطة فعّالة أصلاً.",
    )


def advance_batch_stage(batch: AnimalBatch, *, actor_user_id: int) -> list:
    """تقدّم جماعي بضغطة زر واحدة من مرحلة الحجر لمرحلة الترقيم — يستثني
    تلقائياً أي رأس مستبعدة فردياً (`batch_hold_reason`). التوزيع
    النهائي (مرحلة 3) له دالة منفصلة (`distribute_batch`) لأنه يحتاج
    تحديد حظيرة فعلية لكل رأس، مو تقدّماً تلقائياً بالكامل."""
    if batch.stage != AnimalBatch.STAGE_QUARANTINE:
        raise ValueError("التقدّم الجماعي التلقائي متاح فقط من مرحلة الحجر لمرحلة الترقيم.")
    members = _eligible_members(batch)
    created = [_apply_stage2_tagging(batch, a) for a in members]
    batch.stage = AnimalBatch.STAGE_TAGGING
    db.session.add(batch)
    excluded = len(_active_members(batch)) - len(members)
    db.session.add(AuditLog(
        actor_user_id=actor_user_id, action="batch.advance_stage",
        entity_type="AnimalBatch", entity_id=batch.id,
        details=f"مرحلة 1→2، {len(members)} رأس تقدّمت" + (f"، {excluded} مستبعدة" if excluded else ""),
    ))
    db.session.commit()
    return created


def distribute_batch(batch: AnimalBatch, *, assignments: dict, actor_user_id: int) -> list:
    """المرحلة 3 (نهائية) — assignments: {animal_id: barn_id}. أي رأس
    مستبعدة أو غير موجودة بـ assignments تُستثنى وتبقى لحين تلحق فردياً
    عبر `advance_single_animal` بعد ما تُحرَّر أو تُحدَّد حظيرتها."""
    if batch.stage != AnimalBatch.STAGE_TAGGING:
        raise ValueError("التوزيع النهائي متاح فقط من مرحلة الترقيم/الفحص.")
    created = []
    distributed = 0
    for animal in _eligible_members(batch):
        barn_id = assignments.get(animal.id) or assignments.get(str(animal.id))
        if not barn_id:
            continue
        created.append(_apply_stage3_distribution(batch, animal, int(barn_id)))
        distributed += 1
    batch.stage = AnimalBatch.STAGE_DISTRIBUTED
    db.session.add(batch)
    db.session.add(AuditLog(actor_user_id=actor_user_id, action="batch.distribute",
                             entity_type="AnimalBatch", entity_id=batch.id,
                             details=f"{distributed} رأس وُزِّعت"))
    db.session.commit()
    return created


def hold_animal(animal: Animal, *, reason: str, actor_user_id: int) -> Animal:
    """عزل/استبعاد فردي لرأس مشتبه بها من التقدّم الجماعي التالي —
    تبقى بمرحلتها الحالية (وحظيرتها الحالية، عادة العزل أصلاً) بينما
    تتقدّم بقية الدفعة السليمة."""
    if not animal.batch_id:
        raise ValueError("هذا الرأس مو ضمن أي دفعة استقبال.")
    if not reason:
        raise ValueError("لازم سبب صريح للاستبعاد.")
    animal.batch_hold_reason = reason
    db.session.add(animal)
    db.session.add(AuditLog(actor_user_id=actor_user_id, action="batch.hold_animal",
                             entity_type="Animal", entity_id=animal.id, details=reason))
    db.session.commit()
    return animal


def release_hold(animal: Animal, *, actor_user_id: int) -> Animal:
    if not animal.batch_hold_reason:
        raise ValueError("هذا الرأس مو مستبعدة أصلاً.")
    animal.batch_hold_reason = None
    db.session.add(animal)
    db.session.add(AuditLog(actor_user_id=actor_user_id, action="batch.release_hold",
                             entity_type="Animal", entity_id=animal.id))
    db.session.commit()
    return animal


def advance_single_animal(batch: AnimalBatch, animal: Animal, *, actor_user_id: int, barn_id: int | None = None):
    """لحاق فردي لرأس كانت مستبعدة (بعد تحرير الاستبعاد) بمرحلة دفعتها
    الحالية — يطبّق فقط فعل المرحلة اللي فاتتها، بدون أي تأثير على بقية
    الدفعة."""
    if animal.batch_id != batch.id:
        raise ValueError("هذا الرأس مو من هذي الدفعة.")
    if animal.batch_hold_reason:
        raise ValueError("لازم تحرّر الاستبعاد أولاً قبل التقدّم الفردي.")

    if batch.stage == AnimalBatch.STAGE_TAGGING:
        task = _apply_stage2_tagging(batch, animal)
    elif batch.stage == AnimalBatch.STAGE_DISTRIBUTED:
        if not barn_id:
            raise ValueError("لازم تحدد حظيرة دائمة لهذا الرأس.")
        task = _apply_stage3_distribution(batch, animal, barn_id)
    else:
        raise ValueError("الدفعة لسا بمرحلة الحجر — ما فيه إجراء فردي إضافي مطلوب حالياً.")

    db.session.add(AuditLog(actor_user_id=actor_user_id, action="batch.advance_single_animal",
                             entity_type="Animal", entity_id=animal.id))
    db.session.commit()
    return task
