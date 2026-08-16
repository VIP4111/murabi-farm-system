"""
محرك دورة الإنتاج — يشتق مرحلة كل حيوان تلقائياً من الأدلة الفعلية
(زيارات بيطرية، تقريع، تشخيص حمل...) بدل ما تُحسب أو تُدخل يدوياً.

المبدأ: ProductionWorkflow هو "ذاكرة مؤقتة" (cache) لآخر تقييم، و CycleEvent
هو مصدر الحقيقة. أي إجراء بالنظام يمس دورة حيوان (زيارة بيطرية، تقريع،
تشخيص حمل...) يجب يمر من `record_cycle_event()` — نفس مبدأ نقطة الدخول
الموحّدة اللي بُني عليه `animal_service.create_animal`.

المسار (route) يتحدد مرة وحدة عند أول تقييم للحيوان ولا يُعاد حسابه
تلقائياً بعدها، حتى لو تغيّر الغرض لاحقاً — قرار صريح لتفادي "قفز" التقدّم
لو انعدّل حقل بعد إكمال مراحل فعلية.
"""
from datetime import date
from app.extensions import db
from app.models.animal import Animal, AnimalSource
from app.models.cycle import ProductionWorkflow, CycleEvent


class CycleExitBlocked(Exception):
    """يُرفع لما يُحاول أحد يبيع/يؤرشف حيوان قبل ما يوصل لمرحلة قرار المصير."""


STAGES = [
    (1, "source", "اختيار المصدر"),
    (2, "quarantine", "الحجر والفحص"),
    (3, "breeding_prep", "التجهيز والتقريع"),
    (4, "pregnancy_diagnosis", "تشخيص الحمل"),
    (5, "market_plan", "تخطيط السوق"),
    (6, "pregnancy_management", "إدارة الحمل"),
    (7, "birth_care", "الولادة والرعاية"),
    (8, "lactation_weaning", "الرضاعة والفطام"),
    (9, "evaluation_sorting", "التقييم والفرز"),
    (10, "destiny", "قرار المصير"),
]
STAGE_NAMES = {i: name for i, _, name in STAGES}
STAGE_CODES = {i: code for i, code, _ in STAGES}

ROUTE_STAGES = {
    "closed_exit": [1, 2, 10],
    "fattening": [1, 2, 5, 8, 9, 10],
    "male_breeder": [1, 2, 3, 5, 9, 10],
    "newborn": [1, 2, 7, 8, 9, 10],
    "female_breeding": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "basic_holding": [1, 2, 5, 9, 10],
}

ROUTE_LABELS = {
    "closed_exit": "خارج الدورة",
    "fattening": "تسمين",
    "male_breeder": "فحل تربية",
    "newborn": "مولود",
    "female_breeding": "أنثى تربية",
    "basic_holding": "عام",
}

EVENT_STAGE_MAP = {
    "source": 1,
    "weight": 2, "vet_visit": 2, "disease": 2, "vaccination": 2,
    "mating": 3, "repro_device": 3, "hormone_injection": 3, "twin_estrus_attempt": 3,
    "pregnancy": 4, "sonar": 4,
    "birth": 7,
    "sale": 10, "death": 10, "archive": 10,
}


def _age_days(animal: Animal):
    ref = animal.birth_date or animal.purchase_date or animal.entry_date
    if not ref:
        return None
    return (date.today() - ref).days


def _open_diseases_count(animal: Animal) -> int:
    from app.models import Disease
    return Disease.query.filter_by(animal_id=animal.id, status="active").count()


def _has_confirmed_mating(animal: Animal) -> bool:
    from app.models import Mating, TwinEstrusAttempt, TwinEstrusProgram
    if Mating.query.filter_by(female_id=animal.id).count():
        return True
    return (
        TwinEstrusAttempt.query.join(TwinEstrusProgram)
        .filter(TwinEstrusProgram.ewe_id == animal.id, TwinEstrusAttempt.confirmation_status == "confirmed")
        .count() > 0
    )


def _has_pregnancy_diagnosis(animal: Animal) -> bool:
    from app.models import Pregnancy, SonarResult
    return bool(
        Pregnancy.query.filter_by(female_id=animal.id).count()
        or SonarResult.query.filter_by(ewe_id=animal.id).count()
    )


def _is_confirmed_pregnant(animal: Animal) -> bool:
    from app.models import Pregnancy, SonarResult
    if Pregnancy.query.filter_by(female_id=animal.id, confirmed=True).count():
        return True
    return SonarResult.query.filter_by(ewe_id=animal.id, result="حامل").count() > 0


def _has_health_evidence(animal: Animal) -> bool:
    from app.models import VetVisit, Disease, Vaccination
    return bool(
        VetVisit.query.filter_by(animal_id=animal.id).count()
        or Disease.query.filter_by(animal_id=animal.id).count()
        or Vaccination.query.filter_by(animal_id=animal.id).count()
    )


def determine_route(animal: Animal) -> str:
    from app.models import FarmSettings

    if animal.status != "active":
        return "closed_exit"

    is_young_or_born_here = animal.source == AnimalSource.BIRTH or animal.mother_id is not None
    age = _age_days(animal)
    if is_young_or_born_here and (age is None or age < FarmSettings.get().newborn_route_max_age_days):
        return "newborn"

    if animal.purpose == "تسمين":
        return "fattening"
    if animal.gender == "ذكر" and animal.purpose == "تربية":
        return "male_breeder"
    if animal.gender == "أنثى" and animal.purpose == "تربية":
        return "female_breeding"
    return "basic_holding"


def get_or_create_workflow(animal: Animal) -> ProductionWorkflow:
    wf = animal.workflow
    if wf is None:
        wf = ProductionWorkflow(animal=animal, route=determine_route(animal), current_stage=1)
        db.session.add(wf)
        db.session.flush()
        animal.workflow = wf
    return wf


# ---------- بوابات المراحل: (animal, workflow) -> (passed, missing_items) ----------

def _gate_source(animal, wf):
    missing = []
    if not animal.animal_no:
        missing.append("رقم الحيوان")
    if not (animal.birth_date or animal.purchase_date):
        missing.append("تاريخ الميلاد أو الشراء")
    return (not missing, missing)


def _gate_quarantine(animal, wf):
    """حيوانات وافدة من خارج المزرعة (شراء/هدية) تحتاج فترة حجر فعلية.
    الرصيد الافتتاحي (حيوانات موجودة أصلاً بالقطيع وقت إطلاق النظام) ما
    يحتاج حجر — هو مو "وافد جديد"."""
    from app.models import FarmSettings

    missing = []
    if animal.weight is None:
        missing.append("وزن مسجّل")
    if not _has_health_evidence(animal):
        missing.append("فحص صحي أو زيارة بيطرية أو تطعيم")
    if animal.source in (AnimalSource.PURCHASE, AnimalSource.GIFT):
        entry = animal.purchase_date or animal.entry_date
        if not entry:
            missing.append("تاريخ الدخول")
        else:
            quarantine_days = FarmSettings.get().quarantine_days
            days = (date.today() - entry).days
            if days < quarantine_days:
                missing.append(f"فترة حجر {quarantine_days} يوم من الدخول (باقي {quarantine_days - days} يوم)")
    return (not missing, missing)


def _gate_breeding_prep(animal, wf):
    from app.models import FarmSettings
    fs = FarmSettings.get()

    missing = []
    if animal.weight is None:
        missing.append("وزن مسجّل")
    if _open_diseases_count(animal) > 0:
        missing.append("لا يوجد أمراض مفتوحة")

    age = _age_days(animal)
    if wf.route == "male_breeder":
        from app.models import VetVisit
        has_exam = VetVisit.query.filter_by(animal_id=animal.id).count() > 0
        if not has_exam and not (age is not None and age >= fs.male_fertility_exam_alt_age_days):
            missing.append(f"فحص خصوبة/زيارة بيطرية أو عمر {fs.male_fertility_exam_alt_age_days} يوم فأكثر")
    else:
        if not _has_confirmed_mating(animal) and not (age is not None and age >= fs.min_breeding_age_days):
            missing.append(f"تقريع مسجّل (عادي أو ضمن برنامج) أو عمر {fs.min_breeding_age_days} يوم فأكثر")
    return (not missing, missing)


def _gate_pregnancy_diagnosis(animal, wf):
    missing = []
    if not _has_confirmed_mating(animal):
        missing.append("تقريع مسجّل")
    if not _has_pregnancy_diagnosis(animal):
        missing.append("تشخيص حمل أو فحص سونار")
    return (not missing, missing)


def _gate_market_plan(animal, wf):
    missing = []
    if not wf.target_sale_date and not wf.estimated_value:
        missing.append("تاريخ بيع مستهدف أو قيمة تقديرية (تُملأ بصفحة دورة الإنتاج)")
    return (not missing, missing)


def _gate_pregnancy_management(animal, wf):
    from app.models import VetVisit, SonarResult
    missing = []
    if not _is_confirmed_pregnant(animal):
        missing.append("تأكيد حمل إيجابي (تشخيص أو سونار)")
    if _open_diseases_count(animal) > 0:
        missing.append("لا يوجد أمراض مفتوحة")
    followups = VetVisit.query.filter_by(animal_id=animal.id).count() + SonarResult.query.filter_by(ewe_id=animal.id).count()
    if followups < 1:
        missing.append("متابعة واحدة على الأقل (زيارة بيطرية أو سونار)")
    return (not missing, missing)


def _gate_birth_care(animal, wf):
    """بوابة خروج من العزل (المرحلة 4): وزن + فحص دكتور + تحصين — لكل من
    الأم والمولود، حسب المسار."""
    from app.models import VetVisit, Vaccination

    missing = []
    if wf.route == "newborn":
        if animal.mother_id is None:
            missing.append("مرتبط بأم")
        if animal.birth_date is None:
            missing.append("تاريخ ولادة")
        if animal.weight is None:
            missing.append("وزن عند الولادة")
        if not VetVisit.query.filter_by(animal_id=animal.id).count():
            missing.append("فحص دكتور خلال فترة العزل")
        if not Vaccination.query.filter_by(animal_id=animal.id).count():
            missing.append("تحصين المولود")
    else:
        newest_child = (Animal.query.filter_by(mother_id=animal.id)
                        .order_by(Animal.birth_date.desc()).first())
        if not newest_child:
            missing.append("تسجيل ولادة مرتبطة بهذه الأنثى")
        else:
            since_birth = newest_child.birth_date
            has_postpartum_vaccination = Vaccination.query.filter(
                Vaccination.animal_id == animal.id,
                Vaccination.date >= since_birth,
            ).count() > 0
            if not has_postpartum_vaccination:
                missing.append("تحصين الأم بعد الولادة")
    return (not missing, missing)


def _gate_lactation_weaning(animal, wf):
    from app.models import FarmSettings
    fs = FarmSettings.get()

    missing = []
    age = _age_days(animal)
    if wf.route == "fattening":
        if _open_diseases_count(animal) > 0:
            missing.append("لا يوجد أمراض مفتوحة")
        if not wf.target_sale_date:
            missing.append("تاريخ بيع مستهدف")
    else:
        if age is None or age < fs.weaning_min_age_days:
            missing.append(f"عمر {fs.weaning_min_age_days} يوم فأكثر")
        if not wf.weaning_date and not (age is not None and age >= fs.weaning_alt_age_days):
            missing.append(f"تاريخ فطام أو عمر {fs.weaning_alt_age_days} يوم فأكثر")
    return (not missing, missing)


def _production_score(animal: Animal) -> int:
    score = 100
    if animal.weight is None:
        score -= 20
    if _open_diseases_count(animal) > 0:
        score -= 30
    if not _has_health_evidence(animal):
        score -= 15
    return max(0, score)


def _gate_evaluation_sorting(animal, wf):
    missing = []
    score = _production_score(animal)
    if score < 60:
        missing.append(f"التقييم الإنتاجي منخفض ({score}/100) — راجع الصحة والوزن")
    if _open_diseases_count(animal) > 0:
        missing.append("لا يوجد أمراض مفتوحة")
    return (not missing, missing)


def _gate_destiny(animal, wf):
    if wf.status == "complete":
        return (True, [])
    return (False, ["بانتظار قرار خروج: بيع / نفوق / أرشفة"])


STAGE_GATES = {
    1: _gate_source,
    2: _gate_quarantine,
    3: _gate_breeding_prep,
    4: _gate_pregnancy_diagnosis,
    5: _gate_market_plan,
    6: _gate_pregnancy_management,
    7: _gate_birth_care,
    8: _gate_lactation_weaning,
    9: _gate_evaluation_sorting,
    10: _gate_destiny,
}

# مراحل "دليل فعلي" فقط (سجل تقريع/حمل/سونار/ولادة موجود) — هذي وحدها تعتبر
# "تخطّي غير منتظم" لو صارت قبل ما تكتمل مرحلة أسبق. مراحل 5 و9 بواباتها
# قائمة على غياب مؤشرات سلبية (خطة سوق فاضية، تقييم افتراضي) — تقدر "تعدي"
# بمحض الصدفة على حيوان جديد بدون أي أدلة، فما تُحسب "غير منتظمة" فعلياً.
EVIDENCE_BASED_STAGES = {3, 4, 6, 7}


def evaluate(animal: Animal) -> dict:
    """يعيد تقييم دورة الحيوان بالكامل ضد الأدلة الفعلية، ويحدّث ProductionWorkflow."""
    wf = get_or_create_workflow(animal)

    if wf.destiny_decision:
        # الحيوان خرج من الدورة فعلياً (بيع/نفوق/أرشفة) — قرار الخروج نهائي
        # ولا يخضع لإعادة تقييم البوابات (خصوصاً النفوق اللي ممكن يصير بأي
        # مرحلة). إعادة فحص البوابات هنا كانت تسبب "ترتيب غير منتظم" وهمي.
        wf.current_stage = 10
        wf.stage_name = STAGE_NAMES[10]
        wf.status = "complete"
        wf.missing_items = None
        db.session.add(wf)
        return {
            "route": wf.route, "allowed_stage": 10, "completed_through": 10,
            "first_blocked_stage": None, "cycle_status": "complete",
            "missing_items": [], "out_of_order_count": wf.out_of_order_count,
        }

    active_stages = ROUTE_STAGES[wf.route]
    was_out_of_order = wf.status == "out_of_order"

    completed_through = 0
    first_blocked_stage = None
    missing_for_blocked = []
    out_of_order = False

    for stage_index in range(1, 11):
        if stage_index not in active_stages:
            continue
        passed, missing = STAGE_GATES[stage_index](animal, wf)
        if passed:
            if first_blocked_stage is None:
                completed_through = stage_index
            elif stage_index in EVIDENCE_BASED_STAGES:
                out_of_order = True
        elif first_blocked_stage is None:
            first_blocked_stage = stage_index
            missing_for_blocked = missing

    allowed_stage = first_blocked_stage or max(active_stages)

    if out_of_order:
        status = "out_of_order"
        if not was_out_of_order:
            wf.out_of_order_count = (wf.out_of_order_count or 0) + 1
    elif first_blocked_stage is None:
        status = "complete" if wf.destiny_decision else "active"
    else:
        status = "active"

    wf.current_stage = allowed_stage
    wf.stage_name = STAGE_NAMES[allowed_stage]
    wf.status = status
    wf.missing_items = "|".join(missing_for_blocked[:8]) if missing_for_blocked else None
    db.session.add(wf)

    return {
        "route": wf.route,
        "allowed_stage": allowed_stage,
        "completed_through": completed_through,
        "first_blocked_stage": first_blocked_stage,
        "cycle_status": status,
        "missing_items": missing_for_blocked,
        "out_of_order_count": wf.out_of_order_count,
    }


def record_cycle_event(animal: Animal, event_type: str, *, source_type=None, source_id=None, event_date=None) -> CycleEvent:
    """نقطة الدخول الموحّدة لأي إجراء يمس دورة حيوان — كل الأماكن اللي تسجّل
    زيارة بيطرية/تقريع/تشخيص حمل... يجب تستدعي هذي الدالة بعد الحفظ."""
    event_date = event_date or date.today()
    stage_index = EVENT_STAGE_MAP.get(event_type, 1)
    result = evaluate(animal)
    wf = animal.workflow

    ev = CycleEvent(
        animal_id=animal.id,
        event_type=event_type,
        stage_index=stage_index,
        stage_name=STAGE_NAMES.get(stage_index),
        source_type=source_type,
        source_id=source_id,
        event_date=event_date,
        cycle_status=result["cycle_status"],
        allowed_stage=result["allowed_stage"],
        completed_through=result["completed_through"],
        first_blocked_stage=result["first_blocked_stage"],
        next_required_step=STAGE_NAMES.get(result["first_blocked_stage"]) if result["first_blocked_stage"] else None,
        next_required_fix="؛ ".join(result["missing_items"]) if result["missing_items"] else None,
        out_of_order_count=result["out_of_order_count"],
    )
    db.session.add(ev)
    animal.lifecycle_stage = wf.stage_name
    db.session.add(animal)
    db.session.commit()
    return ev


# ---------- الخروج من الدورة ----------

def assert_exit_allowed(animal: Animal) -> None:
    evaluate(animal)
    wf = animal.workflow
    if wf.current_stage < 10 or wf.status == "out_of_order":
        raise CycleExitBlocked(
            f'الحيوان لسا بمرحلة "{wf.stage_name}" — لازم يوصل لمرحلة "قرار المصير" قبل البيع أو الأرشفة.'
        )

    # حظر آلي على البيع/الذبح أثناء فترة تحريم دواء (بند إضافي 50) —
    # كانت تحذيراً بس بعد البيع (بند 46)، صارت بوابة حقيقية قبله. نقطة
    # دخول واحدة (`sell_animal` يستدعي هذي الدالة) تغطي البيع الفردي
    # والجماعي معاً بدون أي تكرار منطق. الحظر يُرفع تلقائياً بمجرد ما
    # ينتهي التاريخ — الدالة تُحسب حية من الجداول الفعلية، صفر عمود
    # حالة مخزَّن يحتاج تحديثاً يدوياً أو مهمة مجدولة.
    from app.health.health_service import animal_under_withdrawal
    until = animal_under_withdrawal(animal.id)
    if until:
        days_left = (until - date.today()).days
        raise CycleExitBlocked(
            f'"{animal.animal_no}" تحت فترة تحريم دواء حتى {until} (باقي {days_left} يوم) — '
            "ممنوع البيع أو الذبح لين تنتهي الفترة كاملة."
        )


def sell_animal(animal: Animal, *, sale_price: float, actor_user_id: int, sale_date=None, notes=None,
                 buyer_name=None, buyer_phone=None, no_invoice=False):
    from app.models import Finance, AuditLog

    sale_date = sale_date or date.today()
    assert_exit_allowed(animal)
    wf = animal.workflow

    fin = Finance(
        date=sale_date, operation_type="sale", category="بيع رأس",
        item=f"بيع {animal.animal_no}", amount=sale_price, related_animal_id=animal.id,
        buyer_name=buyer_name, buyer_phone=buyer_phone, no_invoice=no_invoice,
    )
    db.session.add(fin)
    animal.status = "sold"
    animal.market_trip_started_at = None  # بند 204 — انباع فعلاً، انتهت رحلة السوق لو كانت قائمة
    animal.market_trip_note = None
    db.session.add(AuditLog(actor_user_id=actor_user_id, action="animal.sell", entity_type="Animal",
                             entity_id=animal.id, details=f"price={sale_price}"))
    db.session.flush()

    wf.destiny_decision = "بيع"
    wf.status = "complete"
    wf.notes = (wf.notes + " | " if wf.notes else "") + (notes or "")
    db.session.add(wf)

    # بند إضافي 98 — أي مهمة مفتوحة لهذا الرأس (تحصين، رش، خطوة بروتوكول
    # علاج...) تُلغى تلقائياً؛ رأس مباع ما له أي عمل ميداني معلَّق يستاهل
    # بقاءه بقوائم العمال اليومية.
    from app.team import task_service
    task_service.cancel_open_tasks_for_animal(animal, reason=f"أُلغيت تلقائياً — الرأس {animal.animal_no} انباع")

    db.session.commit()

    record_cycle_event(animal, "sale", source_type="Finance", source_id=fin.id, event_date=sale_date)
    return fin


def send_to_market(animal: Animal, *, actor_user_id: int, note=None):
    """طلعت الرأس فعلياً من المزرعة تحاول تبيعها بالسوق — بند إضافي 204،
    طلبك بالنص: "كيف أطلّعها من المزرعة وأرجع أسجّل عملية مستمرة أو تم
    البيع؟". نفس بوابة `sell_animal` بالضبط (مرحلة 'قرار المصير' + بلا
    فترة تحريم دواء) — لو ما تقدر تبيعها الحين، ما تقدر تطلّعها للسوق
    أصلاً. ما يغيّر `animal.status` — لسا 'نشط' بكل الأنظمة الثانية."""
    from app.models import AuditLog

    from datetime import datetime, timezone

    assert_exit_allowed(animal)
    animal.market_trip_started_at = datetime.now(timezone.utc)
    animal.market_trip_note = note
    db.session.add(animal)
    db.session.add(AuditLog(actor_user_id=actor_user_id, action="animal.send_to_market",
                             entity_type="Animal", entity_id=animal.id, details=note or ""))
    db.session.commit()


def return_from_market(animal: Animal, *, actor_user_id: int, note=None):
    """رجعت الرأس للمزرعة بدون ما تنباع — يمسح علم "بالسوق" بس، صفر
    تأثير على أي سجل مالي أو حالة ثانية (ما فيه شي يحتاج استرجاع أصلاً
    لأن ما فيه بيع اتسجّل)."""
    from app.models import AuditLog

    animal.market_trip_started_at = None
    animal.market_trip_note = None
    db.session.add(animal)
    db.session.add(AuditLog(actor_user_id=actor_user_id, action="animal.return_from_market",
                             entity_type="Animal", entity_id=animal.id, details=note or ""))
    db.session.commit()


def mark_animal_dead(animal: Animal, *, actor_user_id: int, reason=None, death_date=None):
    """النفوق حقيقة واقعية، مو قرار عمل — يُسجَّل بدون بوابة اكتمال دورة."""
    from app.models import Finance, AuditLog

    death_date = death_date or date.today()
    wf = get_or_create_workflow(animal)

    source_id = None
    if animal.price:
        fin = Finance(
            date=death_date, operation_type="expense", category="خسارة أصل",
            item=f"نفوق {animal.animal_no}", amount=animal.price,
            related_animal_id=animal.id, description=reason,
        )
        db.session.add(fin)
        db.session.flush()
        source_id = fin.id

    animal.status = "dead"
    db.session.add(AuditLog(actor_user_id=actor_user_id, action="animal.death", entity_type="Animal",
                             entity_id=animal.id, details=reason or ""))

    wf.destiny_decision = "نفوق طارئ"
    wf.status = "complete"
    wf.notes = (wf.notes + " | " if wf.notes else "") + (reason or "")
    db.session.add(wf)

    # بند إضافي 98 — نفس منطق sell_animal بالضبط.
    from app.team import task_service
    task_service.cancel_open_tasks_for_animal(animal, reason=f"أُلغيت تلقائياً — الرأس {animal.animal_no} نفق")

    db.session.commit()

    record_cycle_event(animal, "death", source_type="Finance", source_id=source_id, event_date=death_date)


def delete_animal(animal: Animal, *, actor_user_id: int, force: bool = False, reason=None):
    from app.models import Finance, AuditLog

    assert_exit_allowed(animal)
    active_finance = Finance.query.filter_by(related_animal_id=animal.id, is_cancelled=False).count()
    if active_finance and not force:
        raise CycleExitBlocked('يوجد عمليات مالية مرتبطة بهذا الحيوان — فعّل "تجاوز" لو متأكد إنك تبي تكمل.')

    wf = animal.workflow
    animal.status = "deleted"
    db.session.add(AuditLog(actor_user_id=actor_user_id, action="animal.delete", entity_type="Animal",
                             entity_id=animal.id, details=reason or ""))

    wf.destiny_decision = "حذف/أرشفة"
    wf.status = "complete"
    wf.notes = (wf.notes + " | " if wf.notes else "") + (reason or "")
    db.session.add(wf)

    # بند إضافي 98 — نفس منطق sell_animal/mark_animal_dead بالضبط.
    from app.team import task_service
    task_service.cancel_open_tasks_for_animal(animal, reason=f"أُلغيت تلقائياً — الرأس {animal.animal_no} اتحذف/أُرشف")

    db.session.commit()

    record_cycle_event(animal, "archive", event_date=date.today())


def restore_animal_after_sale_cancel(animal: Animal, *, actor_user_id: int):
    """لو أُلغيت عملية بيع، الحيوان يرجع نشط والدورة تُعاد اشتقاقها من الأدلة
    الفعلية (ترجع لآخر مرحلة مؤكّدة تلقائياً، مو تبقى عالقة على 10)."""
    from app.models import AuditLog

    animal.status = "active"
    wf = get_or_create_workflow(animal)
    wf.destiny_decision = None
    db.session.add(animal)
    db.session.add(wf)
    db.session.add(AuditLog(actor_user_id=actor_user_id, action="animal.sale_cancelled_restore",
                             entity_type="Animal", entity_id=animal.id))
    db.session.commit()
    evaluate(animal)
    db.session.commit()
