"""بند إضافي 149 — طلبك (عبر ROADMAP.md بند 6 "ناقص: توليد مهام ذكية
من مصادر ثانية غير العزل — تطعيمات مستحقة عامة، أوزان متأخرة..."):
مصدران جديدان لتوليد مهام تلقائية، بمعزل تماماً عن مسار العزل بعد
الولادة."""
from datetime import date, timedelta

from app.core import scheduled_care_service
from app.core.animal_service import add_weight_record
from app.models import FarmSettings, Task, Vaccination
from app.models.animal import AnimalSource
from factories import make_animal, make_barn


def test_generates_task_for_overdue_general_vaccination(app):
    animal = make_animal(animal_no="VDT-01")
    v = Vaccination(
        animal_id=animal.id, vaccine_name="لقاح تجريبي",
        date=date.today() - timedelta(days=60),
        next_due_date=date.today() - timedelta(days=5),
    )
    from app.extensions import db
    db.session.add(v)
    db.session.commit()

    created = scheduled_care_service.generate_vaccination_due_tasks()
    assert len(created) == 1
    assert created[0].animal_id == animal.id
    assert created[0].task_type == "vaccination_due"


def test_vaccination_due_task_is_idempotent(app):
    animal = make_animal(animal_no="VDT-02")
    from app.extensions import db
    db.session.add(Vaccination(
        animal_id=animal.id, vaccine_name="لقاح تجريبي",
        date=date.today() - timedelta(days=60),
        next_due_date=date.today() - timedelta(days=5),
    ))
    db.session.commit()

    first = scheduled_care_service.generate_vaccination_due_tasks()
    second = scheduled_care_service.generate_vaccination_due_tasks()
    assert len(first) == 1
    assert len(second) == 0


def test_no_vaccination_task_when_not_yet_due(app):
    animal = make_animal(animal_no="VDT-03")
    from app.extensions import db
    db.session.add(Vaccination(
        animal_id=animal.id, vaccine_name="لقاح تجريبي",
        date=date.today(), next_due_date=date.today() + timedelta(days=30),
    ))
    db.session.commit()

    assert scheduled_care_service.generate_vaccination_due_tasks() == []


def test_generates_task_for_overdue_weight_check(app):
    fs = FarmSettings.get()
    animal = make_animal(animal_no="WGT-01")
    add_weight_record(animal=animal, record_date=date.today() - timedelta(days=fs.weight_check_interval_days + 5), weight=30)

    created = scheduled_care_service.generate_overdue_weight_tasks()
    assert len(created) == 1
    assert created[0].animal_id == animal.id
    assert created[0].task_type == "reweigh_followup"


def test_no_weight_task_when_recently_weighed(app):
    animal = make_animal(animal_no="WGT-02")
    add_weight_record(animal=animal, record_date=date.today() - timedelta(days=2), weight=30)

    assert scheduled_care_service.generate_overdue_weight_tasks() == []


def test_weight_task_is_idempotent(app):
    fs = FarmSettings.get()
    animal = make_animal(animal_no="WGT-03")
    add_weight_record(animal=animal, record_date=date.today() - timedelta(days=fs.weight_check_interval_days + 5), weight=30)

    first = scheduled_care_service.generate_overdue_weight_tasks()
    second = scheduled_care_service.generate_overdue_weight_tasks()
    assert len(first) == 1
    assert len(second) == 0


def test_never_weighed_animal_with_old_entry_date_gets_task(app):
    from app.extensions import db
    fs = FarmSettings.get()
    animal = make_animal(animal_no="WGT-04", source=AnimalSource.GIFT)
    animal.entry_date = date.today() - timedelta(days=fs.weight_check_interval_days + 10)
    db.session.add(animal)
    db.session.commit()

    created = scheduled_care_service.generate_overdue_weight_tasks()
    assert any(t.animal_id == animal.id for t in created)
