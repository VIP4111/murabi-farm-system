"""اختبارات فرز الحظائر حسب الحالة الفسيولوجية (بند إضافي 133) — مهمة
تُنشأ فقط عندما يوصل الرأس حالة فعلية (حامل - الشهور الأخيرة/رضاعة) وحظيرته
الحالية غير مطابقة، وبس لو فيه حظيرة فعلية بهذا النوع أصلاً. اتجاه
واحد بس — ما نفحص "رأس بحظيرة غلط" بالعكس."""
from datetime import date, timedelta

from app.extensions import db
from app.core import barn_physiology_service as svc
from app.models import Pregnancy, Task
from app.team import task_service
from factories import make_animal, make_barn


def _make_late_pregnancy(female, days_from_expected_birth):
    expected_birth = date.today() + timedelta(days=days_from_expected_birth)
    p_date = expected_birth - timedelta(days=150)  # FarmSettings.gestation_days default
    p = Pregnancy(female_id=female.id, date=p_date, confirmed=True)
    db.session.add(p)
    db.session.commit()
    return p


def test_late_pregnancy_animal_gets_move_task(app):
    other_barn = make_barn(barn_no="OB-01", barn_type="عادية")
    target_barn = make_barn(barn_no="PB-01", barn_type="حامل - الشهور الأخيرة")
    female = make_animal(animal_no="LP-01", gender="أنثى", barn_id=other_barn.id)
    _make_late_pregnancy(female, days_from_expected_birth=10)  # within 45-day window

    created = svc.generate_barn_move_tasks()
    assert any(t.animal_id == female.id for t in created)


def test_no_task_when_pregnancy_not_yet_late(app):
    other_barn = make_barn(barn_no="OB-02", barn_type="عادية")
    make_barn(barn_no="PB-02", barn_type="حامل - الشهور الأخيرة")
    female = make_animal(animal_no="LP-02", gender="أنثى", barn_id=other_barn.id)
    _make_late_pregnancy(female, days_from_expected_birth=140)  # way before window

    created = svc.generate_barn_move_tasks()
    assert not any(t.animal_id == female.id for t in created)


def test_no_task_when_already_in_correct_barn(app):
    target_barn = make_barn(barn_no="PB-03", barn_type="حامل - الشهور الأخيرة")
    female = make_animal(animal_no="LP-03", gender="أنثى", barn_id=target_barn.id)
    _make_late_pregnancy(female, days_from_expected_birth=10)

    created = svc.generate_barn_move_tasks()
    assert not any(t.animal_id == female.id for t in created)


def test_no_task_when_no_matching_barn_exists(app):
    other_barn = make_barn(barn_no="OB-04", barn_type="عادية")
    female = make_animal(animal_no="LP-04", gender="أنثى", barn_id=other_barn.id)
    _make_late_pregnancy(female, days_from_expected_birth=10)

    created = svc.generate_barn_move_tasks()
    assert not any(t.animal_id == female.id for t in created)


def test_abortion_outcome_excludes_from_late_pregnancy_check(app):
    other_barn = make_barn(barn_no="OB-05", barn_type="عادية")
    make_barn(barn_no="PB-05", barn_type="حامل - الشهور الأخيرة")
    female = make_animal(animal_no="LP-05", gender="أنثى", barn_id=other_barn.id)
    p = _make_late_pregnancy(female, days_from_expected_birth=10)
    p.outcome = "abortion"
    p.outcome_date = date.today()
    db.session.commit()

    created = svc.generate_barn_move_tasks()
    assert not any(t.animal_id == female.id for t in created)


def test_nursing_mother_gets_move_task(app):
    other_barn = make_barn(barn_no="OB-06", barn_type="عادية")
    make_barn(barn_no="NB-01", barn_type="رضاعة")
    mother = make_animal(animal_no="NM-01", gender="أنثى", barn_id=other_barn.id)
    child = make_animal(animal_no="NC-01", gender="ذكر", barn_id=other_barn.id)
    child.mother_id = mother.id
    child.birth_date = date.today() - timedelta(days=10)
    db.session.commit()

    created = svc.generate_barn_move_tasks()
    assert any(t.animal_id == mother.id for t in created)


def test_old_child_does_not_trigger_nursing_task(app):
    other_barn = make_barn(barn_no="OB-07", barn_type="عادية")
    make_barn(barn_no="NB-02", barn_type="رضاعة")
    mother = make_animal(animal_no="NM-02", gender="أنثى", barn_id=other_barn.id)
    child = make_animal(animal_no="NC-02", gender="ذكر", barn_id=other_barn.id)
    child.mother_id = mother.id
    child.birth_date = date.today() - timedelta(days=200)  # older than 90-day nursing window
    db.session.commit()

    created = svc.generate_barn_move_tasks()
    assert not any(t.animal_id == mother.id for t in created)


def test_second_call_same_day_creates_no_duplicate(app):
    other_barn = make_barn(barn_no="OB-08", barn_type="عادية")
    make_barn(barn_no="PB-08", barn_type="حامل - الشهور الأخيرة")
    female = make_animal(animal_no="LP-08", gender="أنثى", barn_id=other_barn.id)
    _make_late_pregnancy(female, days_from_expected_birth=10)

    first = svc.generate_barn_move_tasks()
    second = svc.generate_barn_move_tasks()
    assert any(t.animal_id == female.id for t in first)
    assert not any(t.animal_id == female.id for t in second)


def test_completing_move_task_relocates_animal(app, owner):
    other_barn = make_barn(barn_no="OB-09", barn_type="عادية")
    target_barn = make_barn(barn_no="PB-09", barn_type="حامل - الشهور الأخيرة")
    female = make_animal(animal_no="LP-09", gender="أنثى", barn_id=other_barn.id)
    _make_late_pregnancy(female, days_from_expected_birth=10)

    svc.generate_barn_move_tasks()
    move_task = Task.query.filter_by(animal_id=female.id, task_type="barn_physiology_move").first()
    assert move_task is not None
    move_task.status = "pending"
    move_task.assignee_id = owner.id
    db.session.commit()

    task_service.complete_task(move_task, actor=owner)

    db.session.refresh(female)
    assert female.barn_id == target_barn.id
