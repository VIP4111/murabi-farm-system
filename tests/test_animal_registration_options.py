"""اختبارات تسجيل الحيوان الموسّع (بند إضافي، 2026-07-28): فصيلة جديدة
آمنة (ما تدخل دورة الإنتاج)، حظيرة/لون إلزاميان بالراوت، عزل تلقائي
عند شراء يدخل حظيرة العزل، وحمل عند التسجيل ينقل الحيوان لحظيرة
الحوامل بعد إنجاز مهمة النقل."""
from datetime import date

from app.extensions import db
from app.core.animal_service import create_animal
from app.core.routes import _seed_system_barns
from app.models import Barn, Pregnancy, ProductionWorkflow, Task
from app.models.animal import AnimalSource
from app.team import task_service
from factories import make_barn


def test_new_species_does_not_enter_cycle_engine(app):
    animal = create_animal(
        animal_no="SPX-01", source=AnimalSource.PURCHASE, gender="أنثى",
        species="بقر", purchase_date=date.today(),
    )
    assert ProductionWorkflow.query.filter_by(animal_id=animal.id).first() is None


def test_sheep_goat_still_enters_cycle_engine(app):
    animal = create_animal(
        animal_no="SPX-02", source=AnimalSource.PURCHASE, gender="أنثى",
        species="sheep_goat", purchase_date=date.today(),
    )
    assert ProductionWorkflow.query.filter_by(animal_id=animal.id).first() is not None


def test_seed_system_barns_creates_four_types_once(app):
    _seed_system_barns()
    types = {b.barn_type for b in Barn.query.all()}
    assert {"عزل", "حوامل", "عادية", "عزل_مرض"}.issubset(types)
    count_before = Barn.query.count()
    _seed_system_barns()
    assert Barn.query.count() == count_before


def test_purchase_into_quarantine_barn_generates_starter_tasks(app):
    barn = make_barn(barn_no="QB-01", barn_type="عزل")
    animal = create_animal(
        animal_no="SPX-03", source=AnimalSource.PURCHASE, gender="ذكر",
        barn_id=barn.id, purchase_date=date.today(),
    )
    tasks = Task.query.filter_by(animal_id=animal.id).all()
    task_types = {t.task_type for t in tasks}
    assert "batch_spray" in task_types
    assert "batch_initial_vaccination" in task_types


def test_purchase_into_normal_barn_generates_no_starter_tasks(app):
    barn = make_barn(barn_no="QB-02", barn_type="عادية")
    animal = create_animal(
        animal_no="SPX-04", source=AnimalSource.PURCHASE, gender="ذكر",
        barn_id=barn.id, purchase_date=date.today(),
    )
    assert Task.query.filter_by(animal_id=animal.id).count() == 0


def test_pregnant_at_intake_creates_unconfirmed_pregnancy_and_move_task(app):
    barn = make_barn(barn_no="QB-03", barn_type="عزل")
    animal = create_animal(
        animal_no="SPX-05", source=AnimalSource.PURCHASE, gender="أنثى",
        barn_id=barn.id, purchase_date=date.today(), is_pregnant_at_intake=True,
    )
    pregnancy = Pregnancy.query.filter_by(female_id=animal.id).first()
    assert pregnancy is not None
    assert pregnancy.confirmed is False

    move_task = Task.query.filter_by(animal_id=animal.id, task_type="move_to_pregnant_barn").first()
    assert move_task is not None
    assert move_task.status == "suggested"


def test_completing_move_task_relocates_animal_to_pregnant_barn(app, owner):
    quarantine = make_barn(barn_no="QB-04", barn_type="عزل")
    pregnant_barn = make_barn(barn_no="PB-01", barn_type="حوامل")
    animal = create_animal(
        animal_no="SPX-06", source=AnimalSource.PURCHASE, gender="أنثى",
        barn_id=quarantine.id, purchase_date=date.today(), is_pregnant_at_intake=True,
    )
    move_task = Task.query.filter_by(animal_id=animal.id, task_type="move_to_pregnant_barn").first()
    move_task.status = "pending"
    move_task.assignee_id = owner.id
    db.session.commit()

    task_service.complete_task(move_task, actor=owner)

    db.session.refresh(animal)
    assert animal.barn_id == pregnant_barn.id


def test_male_at_intake_gets_no_pregnancy_popup_effect(app):
    barn = make_barn(barn_no="QB-05", barn_type="عزل")
    animal = create_animal(
        animal_no="SPX-07", source=AnimalSource.PURCHASE, gender="ذكر",
        barn_id=barn.id, purchase_date=date.today(), is_pregnant_at_intake=True,
    )
    assert Pregnancy.query.filter_by(female_id=animal.id).count() == 0


def test_animals_new_route_requires_barn(app, logged_in_client):
    resp = logged_in_client.post("/animals/new", data={
        "source": "purchase", "gender": "ذكر", "species": "sheep_goat",
        "color": "أبيض", "animal_no": "RT-01",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "الحظيرة مطلوبة".encode() in resp.data


def test_animals_new_route_requires_color(app, logged_in_client):
    barn = make_barn(barn_no="RT-BARN", barn_type="عادية")
    resp = logged_in_client.post("/animals/new", data={
        "source": "purchase", "gender": "ذكر", "species": "sheep_goat",
        "barn_id": str(barn.id), "animal_no": "RT-02",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "اللون مطلوب".encode() in resp.data


def test_breeds_new_route_prevents_duplicate(app, logged_in_client):
    logged_in_client.post("/animals/breeds/new", data={"name": "سلالة اختبار"})
    resp = logged_in_client.post("/animals/breeds/new", data={"name": "سلالة اختبار"}, follow_redirects=True)
    assert "موجودة بالقائمة أصلاً".encode() in resp.data
