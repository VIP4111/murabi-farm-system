"""
محرك العمليات الجماعية (بند 17 بالمواصفة الرئيسية).

طلبك كان "بختصار كلشي يصير للحيوان المفرد يصير على الجماعي" — هذا مبدأ
عام واسع جداً يستحيل بناؤه دفعة وحدة بكل وحدة بالنظام (صحة، تكاثر، مالية،
علف...). بنينا "المحرك" (نفس مصطلح 5.4 بالوثيقة: محرك تذاكر يحدد رؤوس
متعددة ثم يطبّق عليها فعل واحد) + تسع عمليات فعلية جاهزة تغطي كل
الأنشطة الميدانية المطلوبة صراحة (بند إضافي، 2026-07-23): وزن، تحصين،
ملاحظة، نقل حظيرة، بيع، نفوق، مرض/علاج، عزل، وفحص سونار.

**قرار نطاق موثّق**: طلبك ذكر "التغذية الجماعية" أيضاً — لكن `FeedMovement`
أصلاً مسجَّلة على مستوى الحظيرة الكاملة (`barn_id`، مو حيوان بحيوان)،
فسحب علف لحظيرة عبر `/feed/movements/new` الموجودة فعلاً **هو أصلاً
إجراء جماعي** يغطي كل رؤوس الحظيرة بعملية واحدة — ما بنينا دالة تكرار
هنا لأنه تكرار حقيقي بدون فائدة، مو نقص تنفيذ. أما الشراء الجماعي
فمختلف شكلاً (إنشاء رؤوس جديدة، مو تطبيق فعل على رؤوس موجودة) — بُني
بدالة منفصلة `apply_bulk_purchase` بأسفل الملف.

كل دالة هنا تعيد قاموس {animal_id: نتيجة أو خطأ} عشان الشاشة تقدر تعرض
لكل رأس شنو صار بالضبط ("لا شيء يختفي بصمت" — نفس مبدأ المالية بالمشروع).
عمليات البيع تحديداً قد تُرفض لرأس معيّن (بوابة اكتمال الدورة) بينما
تنجح لبقية الرؤوس بنفس الطلب — نفس مبدأ عدم التوقف الكامل لخطأ رأس واحد.
"""
from datetime import date
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models import Animal, AuditLog, Barn
from app.models.animal import AnimalSource
from app.core.animal_service import add_weight_record, add_note, create_animal
from app.core import cycle_engine


def apply_bulk_weight(*, animal_ids: list[int], record_date: date,
                       weights_by_id: dict[int, float], notes_by_id: dict[int, str],
                       actor_user_id: int) -> dict:
    results = {}
    for animal_id in animal_ids:
        weight = weights_by_id.get(animal_id)
        if not weight:
            results[animal_id] = "تخطّي — بدون وزن مُدخَل"
            continue
        animal = Animal.query.get(animal_id)
        if not animal:
            results[animal_id] = "غير موجود"
            continue
        add_weight_record(
            animal=animal, record_date=record_date, weight=weight,
            notes=notes_by_id.get(animal_id) or None, recorded_by_id=actor_user_id,
        )
        cycle_engine.evaluate(animal)
        db.session.commit()
        results[animal_id] = f"تم — {weight} كجم"
    return results


def apply_bulk_vaccination(*, animal_ids: list[int], vaccine_name: str, record_date: date,
                            next_due_date: date | None, pharmacy_id: int | None,
                            quantity_used_per_head: float | None, actor_user_id: int) -> dict:
    from app.health import health_service
    from app.models import Pharmacy, FarmSettings

    pharmacy = Pharmacy.query.get(int(pharmacy_id)) if pharmacy_id else None
    redose_days = FarmSettings.get().antiparasitic_redose_days
    results = {}
    for animal_id in animal_ids:
        animal = Animal.query.get(animal_id)
        if not animal:
            results[animal_id] = "غير موجود"
            continue
        # حارس منع تكرار جرعة الطفيليات (بند إضافي 50) — بلا خيار تجاوز
        # بمستوى الدفعة الجماعية (يحتاج سبباً صريحاً لكل رأس)؛ لو الطبيب
        # متأكد من التكرار لرأس معيّن، يسجّله فردياً بشاشة التطعيم العادية.
        guard = health_service.redose_guard_warning(animal_id=animal_id, pharmacy=pharmacy, redose_days=redose_days)
        if guard:
            results[animal_id] = f"مرفوض — {guard['message']}"
            continue
        try:
            health_service.record_vaccination(
                actor_user_id=actor_user_id, animal_id=animal_id, vaccine_name=vaccine_name,
                date_=record_date, next_due_date=next_due_date,
                pharmacy_id=pharmacy_id, quantity_used=quantity_used_per_head,
            )
            results[animal_id] = "تم"
        except health_service.IncompleteRecordError as e:
            # سلامة المخزون (بند إضافي، 2026-07-23): كمية مشتركة لكل رأس —
            # لو المخزون خلص بمنتصف الدفعة، الرؤوس السابقة تبقى مسجَّلة
            # صح والباقي يُرفض برسالة واضحة، بدل ما يكسر الطلب كامل.
            results[animal_id] = f"مرفوض — {e}"
    return results


def apply_bulk_note(*, animal_ids: list[int], general_note: str, note_date: date,
                     extra_notes_by_id: dict[int, str], actor_user_id: int) -> dict:
    results = {}
    for animal_id in animal_ids:
        animal = Animal.query.get(animal_id)
        if not animal:
            results[animal_id] = "غير موجود"
            continue
        extra = extra_notes_by_id.get(animal_id)
        full_note = f"{general_note} — {extra}" if extra else general_note
        add_note(animal=animal, note_date=note_date, note=full_note, created_by_id=actor_user_id)
        results[animal_id] = "تم"
    return results


def apply_bulk_barn_move(*, animal_ids: list[int], barn_id: int, actor_user_id: int) -> dict:
    results = {}
    for animal_id in animal_ids:
        animal = Animal.query.get(animal_id)
        if not animal:
            results[animal_id] = "غير موجود"
            continue
        old_barn = animal.barn_id
        animal.barn_id = barn_id
        db.session.add(animal)
        db.session.add(AuditLog(
            actor_user_id=actor_user_id, action="animal.bulk_barn_move",
            entity_type="Animal", entity_id=animal.id,
            details=f"barn {old_barn} -> {barn_id}",
        ))
        results[animal_id] = "تم النقل"
    db.session.commit()
    return results


def apply_bulk_sale(*, animal_ids: list[int], sale_date: date,
                     prices_by_id: dict[int, float], notes: str | None, actor_user_id: int) -> dict:
    results = {}
    for animal_id in animal_ids:
        price = prices_by_id.get(animal_id)
        if not price:
            results[animal_id] = "تخطّي — بدون سعر مُدخَل"
            continue
        animal = Animal.query.get(animal_id)
        if not animal:
            results[animal_id] = "غير موجود"
            continue
        try:
            cycle_engine.sell_animal(
                animal, sale_price=price, actor_user_id=actor_user_id,
                sale_date=sale_date, notes=notes,
            )
            results[animal_id] = f"تم البيع — {price}"
        except cycle_engine.CycleExitBlocked as e:
            # يشمل الآن حظر فترة التحريم أيضاً (بند إضافي 50).
            results[animal_id] = f"مرفوض — {e}"
    return results


def apply_bulk_mark_dead(*, animal_ids: list[int], death_date: date,
                          reason: str | None, actor_user_id: int) -> dict:
    results = {}
    for animal_id in animal_ids:
        animal = Animal.query.get(animal_id)
        if not animal:
            results[animal_id] = "غير موجود"
            continue
        cycle_engine.mark_animal_dead(
            animal, actor_user_id=actor_user_id, reason=reason, death_date=death_date,
        )
        results[animal_id] = "تم تسجيل النفوق"
    return results


def apply_bulk_disease(*, animal_ids: list[int], disease_name: str, record_date: date, severity: str | None,
                        pharmacy_id: int | None, quantity_used_per_head: float | None,
                        actor_user_id: int) -> dict:
    from app.health import health_service
    from app.models import Pharmacy, FarmSettings

    pharmacy = Pharmacy.query.get(int(pharmacy_id)) if pharmacy_id else None
    redose_days = FarmSettings.get().antiparasitic_redose_days
    results = {}
    for animal_id in animal_ids:
        animal = Animal.query.get(animal_id)
        if not animal:
            results[animal_id] = "غير موجود"
            continue
        guard = health_service.redose_guard_warning(animal_id=animal_id, pharmacy=pharmacy, redose_days=redose_days)
        if guard:
            results[animal_id] = f"مرفوض — {guard['message']}"
            continue
        try:
            health_service.record_disease(
                actor_user_id=actor_user_id, animal_id=animal_id, disease_name=disease_name,
                date_=record_date, severity=severity,
                pharmacy_id=pharmacy_id, quantity_used=quantity_used_per_head,
            )
            results[animal_id] = "تم تسجيل الحالة"
        except health_service.IncompleteRecordError as e:
            results[animal_id] = f"مرفوض — {e}"
    return results


def apply_bulk_isolation(*, animal_ids: list[int], reason: str | None, note_date: date,
                          actor_user_id: int) -> dict:
    """عزل جماعي: نقل الدفعة كاملة لحظيرة العزل (نفس منطق `barn_type='عزل'`
    اللي تستخدمه خطة العزل التلقائية بعد الولادة، `isolation_service.py`)
    + ملاحظة سبب اختيارية على كل رأس. **ما نغيّر أي حقل "حالة صحية"** لأن
    الجدول ما فيه هذا الحقل أصلاً على `Animal` — الحالة الصحية تُقرأ من
    السجلات الفعلية (أمراض/زيارات مفتوحة)، نفس مبدأ باقي النظام."""
    isolation_barn = Barn.query.filter_by(barn_type="عزل").order_by(Barn.id).first()
    if not isolation_barn:
        return {aid: "مرفوض — ما فيه حظيرة عزل معرَّفة بالنظام" for aid in animal_ids}

    results = {}
    for animal_id in animal_ids:
        animal = Animal.query.get(animal_id)
        if not animal:
            results[animal_id] = "غير موجود"
            continue
        old_barn = animal.barn_id
        animal.barn_id = isolation_barn.id
        db.session.add(animal)
        db.session.add(AuditLog(
            actor_user_id=actor_user_id, action="animal.bulk_isolation",
            entity_type="Animal", entity_id=animal.id,
            details=f"barn {old_barn} -> {isolation_barn.id} — {reason or ''}",
        ))
        if reason:
            add_note(animal=animal, note_date=note_date, note=f"عزل جماعي — {reason}", created_by_id=actor_user_id)
        results[animal_id] = f"تم العزل بحظيرة {isolation_barn.barn_name}"
    db.session.commit()
    return results


def apply_bulk_sonar(*, animal_ids: list[int], exam_date: date, result_by_id: dict[int, str],
                      embryo_count_by_id: dict[int, int], doctor_id: int | None, actor_user_id: int) -> dict:
    from app.models import SonarResult
    from app.core.cycle_engine import record_cycle_event
    results = {}
    for animal_id in animal_ids:
        animal = Animal.query.get(animal_id)
        if not animal:
            results[animal_id] = "غير موجود"
            continue
        row = SonarResult(
            ewe_id=animal_id, exam_date=exam_date,
            result=result_by_id.get(animal_id), embryo_count=embryo_count_by_id.get(animal_id),
            doctor_id=doctor_id,
        )
        db.session.add(row)
        db.session.flush()
        db.session.add(AuditLog(actor_user_id=actor_user_id, action="sonar.bulk_create",
                                 entity_type="SonarResult", entity_id=row.id))
        record_cycle_event(animal, "sonar", source_type="SonarResult", source_id=row.id, event_date=exam_date)
        results[animal_id] = f"تم — {row.result or 'بدون نتيجة محدَّدة'}"
    db.session.commit()
    return results


def apply_bulk_purchase(*, rows: list[dict], barn_id: int | None, purchase_date: date,
                         species: str, actor_user_id: int) -> dict:
    """شراء دفعة جديدة كاملة بضغطة واحدة — مختلف شكلاً عن باقي دوال هذا
    الملف: يُنشئ رؤوساً جديدة (`create_animal`)، ما يطبّق فعل على رؤوس
    موجودة. كل صف بـ`rows` قاموس {animal_no, gender, weight, price}.
    يمر بنفس نقطة الدخول الموحّدة `create_animal` — نفس قيد الحركة
    المالية التلقائية للشراء (بند 18) ونفس تسجيل حدث دورة الإنتاج."""
    results = {}
    for row in rows:
        animal_no = (row.get("animal_no") or "").strip()
        if not animal_no:
            continue
        try:
            animal = create_animal(
                animal_no=animal_no, source=AnimalSource.PURCHASE, gender=row["gender"],
                species=species, barn_id=barn_id, purchase_date=purchase_date,
                weight=row.get("weight"), price=row.get("price"),
            )
        except ValueError as e:
            results[animal_no] = f"مرفوض — {e}"
            continue
        except IntegrityError:
            db.session.rollback()
            results[animal_no] = "مرفوض — الرقم مستخدم من قبل"
            continue
        db.session.add(AuditLog(actor_user_id=actor_user_id, action="animal.bulk_purchase",
                                 entity_type="Animal", entity_id=animal.id))
        db.session.commit()
        results[animal_no] = "تمت الإضافة"
    return results
