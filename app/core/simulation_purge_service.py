"""أداة تنظيف بيانات المحاكاة (بند إضافي 181) — **قرار تصميم صريح**:
هذي ليست "إعادة ضبط مصنع" تمسح كل قاعدة البيانات — زر بضغطة وحدة
يمسح تاريخ مزرعة كامل بدون رجعة خطر حقيقي (حادثة واحدة: ضغطة غلط،
جلسة مخترقة، عامل يخلط = كارثة لا تُرد). بدلها: حذف **مستهدف** لكل
سجل أنشأه `flask simulate-farm-month` تحديداً — يُعرَف بدقة عبر
بادئة `animal_no` الثابتة (`SIM-`) وبادئة `Task.source_type`
(`FarmSimulation`)، صفر لمس لأي بيانات حقيقية بأي حال.

النطاق يشمل كل جدول له علاقة مباشرة بحيوان محاكاة: المالية، التقريع،
الأمراض، المهام، وأحداث/حالة دورة الإنتاج — بترتيب يحترم مفاتيح
الربط الخارجية (يحذف الأبناء قبل الآباء)."""
from app.extensions import db
from app.models import (
    Animal, Finance, Mating, Disease, Task, VetVisit, Vaccination,
    AnimalWeight, AnimalNote,
)
from app.models.cycle import ProductionWorkflow, CycleEvent

SIMULATION_ANIMAL_PREFIX = "SIM-"
SIMULATION_TASK_SOURCE = "FarmSimulation"


def preview_simulation_data() -> dict:
    """عدد كل ما راح يُحذف — تُعرض للمالك قبل التأكيد، بدون أي حذف فعلي."""
    animal_ids = [a.id for a in Animal.query.filter(Animal.animal_no.like(f"{SIMULATION_ANIMAL_PREFIX}%")).all()]
    return {
        "animals": len(animal_ids),
        "finance_rows": Finance.query.filter(Finance.related_animal_id.in_(animal_ids)).count() if animal_ids else 0,
        "matings": Mating.query.filter(
            db.or_(Mating.female_id.in_(animal_ids), Mating.male_id.in_(animal_ids))
        ).count() if animal_ids else 0,
        "diseases": Disease.query.filter(Disease.animal_id.in_(animal_ids)).count() if animal_ids else 0,
        "tasks": Task.query.filter(Task.source_type == SIMULATION_TASK_SOURCE).count(),
    }


def purge_simulation_data() -> dict:
    """يحذف فعلياً كل بيانات المحاكاة — يرجّع نفس تركيبة `preview_simulation_data`
    بعدد ما اتحذف فعلاً، للتأكيد النهائي بالتقرير."""
    animal_ids = [a.id for a in Animal.query.filter(Animal.animal_no.like(f"{SIMULATION_ANIMAL_PREFIX}%")).all()]
    counts = {"animals": len(animal_ids), "finance_rows": 0, "matings": 0, "diseases": 0, "tasks": 0}

    counts["tasks"] = Task.query.filter(Task.source_type == SIMULATION_TASK_SOURCE).delete(synchronize_session=False)

    if animal_ids:
        counts["finance_rows"] = Finance.query.filter(
            Finance.related_animal_id.in_(animal_ids)
        ).delete(synchronize_session=False)
        counts["matings"] = Mating.query.filter(
            db.or_(Mating.female_id.in_(animal_ids), Mating.male_id.in_(animal_ids))
        ).delete(synchronize_session=False)
        counts["diseases"] = Disease.query.filter(Disease.animal_id.in_(animal_ids)).delete(synchronize_session=False)
        VetVisit.query.filter(VetVisit.animal_id.in_(animal_ids)).delete(synchronize_session=False)
        Vaccination.query.filter(Vaccination.animal_id.in_(animal_ids)).delete(synchronize_session=False)
        AnimalWeight.query.filter(AnimalWeight.animal_id.in_(animal_ids)).delete(synchronize_session=False)
        AnimalNote.query.filter(AnimalNote.animal_id.in_(animal_ids)).delete(synchronize_session=False)
        Task.query.filter(Task.animal_id.in_(animal_ids)).delete(synchronize_session=False)
        CycleEvent.query.filter(CycleEvent.animal_id.in_(animal_ids)).delete(synchronize_session=False)
        ProductionWorkflow.query.filter(ProductionWorkflow.animal_id.in_(animal_ids)).delete(synchronize_session=False)
        Animal.query.filter(Animal.id.in_(animal_ids)).delete(synchronize_session=False)

    db.session.commit()
    return counts
