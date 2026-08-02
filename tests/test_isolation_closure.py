"""بند إضافي 102 — إغلاق تلقائي لخطة العزل بعد الولادة. قبل هذا البند،
سلسلة "فحص عزل يومي" كانت تتوقف بصمت بعد آخر يوم، بدون مهمة ختامية."""
from datetime import date

from app.extensions import db
from app.core.animal_service import create_animal, register_birth
from app.models import Task, FarmSettings, User, Role
from app.models.animal import AnimalSource
from app.team import task_service
from factories import make_animal


def _actor():
    role = Role.query.filter_by(name="owner").first()
    user = User(name="دكتور اختبار عزل", phone="0500000098", role_id=role.id)
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def _one_day_isolation():
    settings = FarmSettings.get()
    settings.isolation_days = 1
    db.session.commit()


def test_release_check_task_created_after_last_isolation_check_done(app):
    _one_day_isolation()
    mother = make_animal(animal_no="ISO-M-01", gender="أنثى")
    newborn = register_birth(mother=mother, gender="أنثى", weight=3.0)

    checks = Task.query.filter_by(task_type="isolation_check", animal_id=newborn.id).all()
    assert len(checks) == 1
    actor = _actor()
    checks[0].assignee_id = actor.id
    checks[0].status = "pending"
    db.session.commit()

    task_service.complete_task(checks[0], actor=actor)

    release = Task.query.filter_by(task_type="isolation_release_check", animal_id=newborn.id).first()
    assert release is not None
    assert release.status == "suggested"
    assert newborn.animal_no in release.title
    assert mother.animal_no in release.title


def test_no_release_task_while_isolation_checks_still_open(app):
    settings = FarmSettings.get()
    settings.isolation_days = 3
    db.session.commit()
    mother = make_animal(animal_no="ISO-M-02", gender="أنثى")
    newborn = register_birth(mother=mother, gender="ذكر", weight=3.0)

    checks = Task.query.filter_by(task_type="isolation_check", animal_id=newborn.id).order_by(Task.due_date).all()
    assert len(checks) == 3
    actor = _actor()
    checks[0].assignee_id = actor.id
    checks[0].status = "pending"
    db.session.commit()

    task_service.complete_task(checks[0], actor=actor)

    release = Task.query.filter_by(task_type="isolation_release_check", animal_id=newborn.id).first()
    assert release is None


def test_release_task_completion_does_not_recreate_itself(app):
    _one_day_isolation()
    mother = make_animal(animal_no="ISO-M-03", gender="أنثى")
    newborn = register_birth(mother=mother, gender="أنثى", weight=3.0)

    check = Task.query.filter_by(task_type="isolation_check", animal_id=newborn.id).first()
    actor = _actor()
    check.assignee_id = actor.id
    check.status = "pending"
    db.session.commit()
    task_service.complete_task(check, actor=actor)

    release = Task.query.filter_by(task_type="isolation_release_check", animal_id=newborn.id).first()
    release.assignee_id = actor.id
    release.status = "pending"
    db.session.commit()
    task_service.complete_task(release, actor=actor)

    releases = Task.query.filter_by(task_type="isolation_release_check", animal_id=newborn.id).all()
    assert len(releases) == 1
