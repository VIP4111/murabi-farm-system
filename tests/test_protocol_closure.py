"""بند إضافي 101 — إغلاق تلقائي لتطبيق بروتوكول العلاج. قبل هذا البند،
كل خطوات بروتوكول تخلص بدون أي مهمة "تقييم فعالية العلاج"."""
from datetime import date

from app.extensions import db
from app.core import protocol_service
from app.models import Task, TreatmentProtocol, TreatmentProtocolStep, User, Role
from app.team import task_service
from factories import make_animal, make_pharmacy


def _make_protocol(name="بروتوكول اختبار", steps=None):
    protocol = TreatmentProtocol(name=name)
    db.session.add(protocol)
    db.session.flush()
    for day_offset, title, pharmacy, qty, kind in (steps or []):
        db.session.add(TreatmentProtocolStep(
            protocol_id=protocol.id, day_offset=day_offset, step_title=title,
            pharmacy_id=pharmacy.id, quantity=qty, treatment_kind=kind,
        ))
    db.session.commit()
    return protocol


def _actor(task):
    role = Role.query.filter_by(name="owner").first()
    user = User(name="دكتور اختبار", phone="0500000099", role_id=role.id)
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    task.assignee_id = user.id
    task.status = "pending"
    db.session.commit()
    return user


def test_review_task_created_after_last_step_done(app):
    animal = make_animal(animal_no="PC-01")
    med = make_pharmacy(name="دواء اختبار", withdrawal_days=0)
    protocol = _make_protocol(steps=[(0, "خطوة 1", med, 1, "vaccination")])
    application = protocol_service.apply_protocol(
        protocol, animal_id=animal.id, start_date=date.today(), actor_user_id=1,
    )
    step_task = protocol_service.protocol_application_tasks(application)[0]
    actor = _actor(step_task)

    task_service.complete_task(step_task, actor=actor)

    review = Task.query.filter_by(task_type="protocol_effectiveness_review", animal_id=animal.id).first()
    assert review is not None
    assert review.status == "suggested"
    assert protocol.name in review.title


def test_no_review_task_while_steps_still_open(app):
    animal = make_animal(animal_no="PC-02")
    med = make_pharmacy(name="دواء اختبار 2", withdrawal_days=0)
    protocol = _make_protocol(steps=[
        (0, "خطوة 1", med, 1, "vaccination"),
        (3, "خطوة 2", med, 1, "vaccination"),
    ])
    application = protocol_service.apply_protocol(
        protocol, animal_id=animal.id, start_date=date.today(), actor_user_id=1,
    )
    step1, step2 = protocol_service.protocol_application_tasks(application)
    actor = _actor(step1)

    task_service.complete_task(step1, actor=actor)

    review = Task.query.filter_by(task_type="protocol_effectiveness_review", animal_id=animal.id).first()
    assert review is None  # لسا خطوة 2 مفتوحة


def test_failed_step_also_counts_toward_closure(app):
    animal = make_animal(animal_no="PC-03")
    med = make_pharmacy(name="دواء اختبار 3", withdrawal_days=0)
    protocol = _make_protocol(steps=[(0, "خطوة وحيدة", med, 1, "vaccination")])
    application = protocol_service.apply_protocol(
        protocol, animal_id=animal.id, start_date=date.today(), actor_user_id=1,
    )
    step_task = protocol_service.protocol_application_tasks(application)[0]
    actor = _actor(step_task)

    task_service.fail_task(step_task, actor=actor, reason="نقص الأدوات")

    review = Task.query.filter_by(task_type="protocol_effectiveness_review", animal_id=animal.id).first()
    assert review is not None


def test_review_task_completion_does_not_recreate_itself(app):
    animal = make_animal(animal_no="PC-04")
    med = make_pharmacy(name="دواء اختبار 4", withdrawal_days=0)
    protocol = _make_protocol(steps=[(0, "خطوة", med, 1, "vaccination")])
    application = protocol_service.apply_protocol(
        protocol, animal_id=animal.id, start_date=date.today(), actor_user_id=1,
    )
    step_task = protocol_service.protocol_application_tasks(application)[0]
    actor = _actor(step_task)
    task_service.complete_task(step_task, actor=actor)

    review = Task.query.filter_by(task_type="protocol_effectiveness_review", animal_id=animal.id).first()
    review.assignee_id = actor.id
    review.status = "pending"
    db.session.commit()

    task_service.complete_task(review, actor=actor)

    reviews = Task.query.filter_by(task_type="protocol_effectiveness_review", animal_id=animal.id).all()
    assert len(reviews) == 1
