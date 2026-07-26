"""
تطبيق قوالب بروتوكول العلاج على رأس محدد (بند إضافي 52) — كل خطوة
بالبروتوكول تتحوّل لمهمة "علاج مخطَّط" مستقلة (بنفس آلية `Task.planned_
pharmacy_id/planned_quantity/planned_treatment_kind` من بند 50 بالضبط)،
مستحقة بتاريخ `start_date + day_offset`. الخصم الفعلي من الصيدلية
وفترة السحب (الأطول بين كل أدوية البروتوكول تلقائياً، عبر `animal_
under_withdrawal` الموجود أصلاً) ما يصيران إلا لحظة "تأكيد التنفيذ"
لكل خطوة بشاشة التسجيل الطبي الحقيقية — صفر كود إضافي لهذا الجزء.
"""
from datetime import date, timedelta
from app.extensions import db
from app.models import ProtocolApplication, TreatmentProtocol
from app.team import task_service


def apply_protocol(protocol: TreatmentProtocol, *, animal_id: int, start_date: date,
                    actor_user_id: int) -> ProtocolApplication:
    from app.models import Animal
    animal = Animal.query.get(animal_id)

    application = ProtocolApplication(
        protocol_id=protocol.id, animal_id=animal_id,
        start_date=start_date, applied_by_id=actor_user_id,
    )
    db.session.add(application)
    db.session.flush()

    for step in protocol.steps:
        due = start_date + timedelta(days=step.day_offset)
        task = task_service.create_suggested_task(
            title=f'💊 {protocol.name} — {step.step_title} (يوم {step.day_offset})'
                  + (f' — {animal.animal_no}' if animal else ''),
            task_type="protocol_step",
            barn_id=animal.barn_id if animal else None,
            animal_id=animal_id,
            due_date=due,
            source_type="ProtocolApplication", source_id=application.id,
            notes=f'خطوة ضمن بروتوكول "{protocol.name}" — راجع شاشة تفصيل المهمة للجرعة والمخزون.',
        )
        # ربط الخطوة بدواء/كمية محدَّدة (نفس نمط `apply_bulk_treatment_plan`
        # ببند 50 بالضبط) — هذا اللي يفعّل معاينة المخزون بشاشة تفصيل
        # المهمة، ويجعل "تأكيد التنفيذ" يفتح النموذج معبّأً مسبقاً.
        task.planned_pharmacy_id = step.pharmacy_id
        task.planned_quantity = step.quantity
        task.planned_treatment_kind = step.treatment_kind

    db.session.commit()
    return application


def protocol_application_tasks(application: ProtocolApplication):
    """كل مهام الخطوات المولَّدة لتطبيق بروتوكول معيّن — نفس نمط
    `task_service.batch_siblings` بالضبط، عبر (source_type, source_id)."""
    from app.models import Task
    return (Task.query
            .filter_by(source_type="ProtocolApplication", source_id=application.id)
            .order_by(Task.due_date, Task.id).all())
