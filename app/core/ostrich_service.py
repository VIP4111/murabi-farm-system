"""
خدمة النعام (بند 23 بالمواصفة الرئيسية) — دورة (بيض → حضانة → فقس →
تسجيل فرخ). نفس مبدأ نقطة الدخول الموحّدة المعتمد بالمشروع: أي فرخ ناجح
لازم يمر من `record_hatch_success()` هنا، ما يُنشأ مباشرة بجدول Animal.
"""
from datetime import date, timedelta
from app.extensions import db
from app.models import Animal, AuditLog
from app.models.animal import AnimalSource
from app.models.ostrich import Incubator, OstrichEgg


def register_egg(*, mother_id: int, lay_date: date, quality: str | None = None,
                  weight_grams: float | None = None, notes: str | None = None) -> OstrichEgg:
    egg = OstrichEgg(mother_id=mother_id, lay_date=lay_date, quality=quality,
                      weight_grams=weight_grams, notes=notes)
    db.session.add(egg)
    db.session.commit()
    return egg


def place_in_incubator(egg: OstrichEgg, *, incubator_id: int, incubation_start_date: date) -> OstrichEgg:
    egg.incubator_id = incubator_id
    egg.incubation_start_date = incubation_start_date
    db.session.add(egg)
    db.session.commit()
    return egg


def expected_hatch_date(egg: OstrichEgg, incubation_days: int) -> date | None:
    if not egg.incubation_start_date:
        return None
    return egg.incubation_start_date + timedelta(days=incubation_days)


def record_hatch_success(egg: OstrichEgg, *, actual_hatch_date: date, animal_no: str,
                          gender: str | None = None, weight: float | None = None,
                          actor_user_id: int | None = None) -> Animal:
    from app.core.animal_service import create_animal

    chick = create_animal(
        animal_no=animal_no, source=AnimalSource.BIRTH, gender=gender or None,
        species="ostrich", mother_id=egg.mother_id, birth_date=actual_hatch_date,
        weight=weight, barn_id=egg.mother.barn_id if egg.mother else None,
    )
    egg.hatch_result = "hatched"
    egg.actual_hatch_date = actual_hatch_date
    egg.hatched_animal_id = chick.id
    db.session.add(egg)
    db.session.add(AuditLog(actor_user_id=actor_user_id, action="ostrich_egg.hatch",
                             entity_type="OstrichEgg", entity_id=egg.id, details=f"animal={chick.animal_no}"))
    db.session.commit()
    return chick


def record_hatch_failure(egg: OstrichEgg, *, fail_reason: str, actor_user_id: int | None = None) -> OstrichEgg:
    egg.hatch_result = "failed"
    egg.fail_reason = fail_reason
    db.session.add(egg)
    db.session.add(AuditLog(actor_user_id=actor_user_id, action="ostrich_egg.fail",
                             entity_type="OstrichEgg", entity_id=egg.id, details=fail_reason))
    db.session.commit()
    return egg


def create_incubator(*, code: str, name: str | None = None, capacity: int | None = None,
                      notes: str | None = None) -> Incubator:
    incubator = Incubator(code=code, name=name, capacity=capacity, notes=notes)
    db.session.add(incubator)
    db.session.commit()
    return incubator
