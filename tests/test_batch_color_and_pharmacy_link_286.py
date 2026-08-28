"""بند إضافي 286 — طلبك الصريح "ابحث عن فجوات" بعد بند 285: شاشة
"استقبال دفعة" (Batches) عندها نفس فجوتي الاستقبال الجماعي بالضبط:
(1) الفورم ما فيه حقل لون إطلاقاً رغم إن الكود الخلفي جاهز يستقبله،
(2) مهمتي رش/تحصين مسارها كود منفصل تماماً عن بند 283، فما استفادت
من ربط المخزون الفعلي."""
from datetime import date

from app.extensions import db
from app.core import batch_service
from app.models import Animal, FarmSettings, Task
from factories import make_barn, make_pharmacy


def _quarantine_barn():
    return make_barn(barn_no="QB-286", barn_type="عزل")


def test_create_batch_rejects_entry_without_color(app):
    _quarantine_barn()
    try:
        batch_service.create_batch(
            source="purchase", arrival_date=date.today(), notes=None,
            actor_user_id=1, entries=[{"animal_no": "NB-01", "gender": "أنثى"}],
        )
        assert False, "expected ValueError"
    except ValueError as e:
        assert "لازم تحدد اللون" in str(e)
    assert Animal.query.filter_by(animal_no="NB-01").first() is None


def test_create_batch_saves_chosen_color(app):
    _quarantine_barn()
    batch = batch_service.create_batch(
        source="purchase", arrival_date=date.today(), notes=None,
        actor_user_id=1, entries=[{"animal_no": "NB-02", "gender": "أنثى", "color": "أسود"}],
    )
    animal = Animal.query.filter_by(animal_no="NB-02").first()
    assert animal is not None
    assert animal.color == "أسود"
    assert batch.batch_no


def test_batch_spray_task_not_linked_when_no_default_configured(app):
    _quarantine_barn()
    batch_service.create_batch(
        source="purchase", arrival_date=date.today(), notes=None,
        actor_user_id=1, entries=[{"animal_no": "NB-03", "gender": "أنثى", "color": "أبيض"}],
    )
    animal = Animal.query.filter_by(animal_no="NB-03").first()
    spray_task = Task.query.filter_by(task_type="batch_spray", animal_id=animal.id).first()
    assert spray_task.planned_pharmacy_id is None


def test_batch_spray_and_vaccine_tasks_linked_to_default_pharmacy(app):
    spray = make_pharmacy(name="رشة دفعة اختبار", available_qty=50)
    vaccine = make_pharmacy(name="لقاح دفعة اختبار", available_qty=30)
    fs = FarmSettings.get()
    fs.default_intake_spray_pharmacy_id = spray.id
    fs.default_intake_vaccine_pharmacy_id = vaccine.id
    db.session.commit()

    _quarantine_barn()
    batch_service.create_batch(
        source="purchase", arrival_date=date.today(), notes=None,
        actor_user_id=1, entries=[{"animal_no": "NB-04", "gender": "أنثى", "color": "بني"}],
    )
    animal = Animal.query.filter_by(animal_no="NB-04").first()
    spray_task = Task.query.filter_by(task_type="batch_spray", animal_id=animal.id).first()
    vaccine_task = Task.query.filter_by(task_type="batch_initial_vaccination", animal_id=animal.id).first()

    assert spray_task.planned_pharmacy_id == spray.id
    assert spray_task.planned_treatment_kind == "vet_visit"
    assert vaccine_task.planned_pharmacy_id == vaccine.id
    assert vaccine_task.planned_treatment_kind == "vaccination"


def test_batches_new_form_shows_color_column(app, logged_in_client):
    """بند إضافي 288 — طلبك الصريح "حطلي ألوان بدل الكتابة"."""
    resp = logged_in_client.get("/batches/new")
    body = resp.data.decode()
    assert 'name="color_0"' in body
    assert "colorChip" in body


def test_batches_new_route_rejects_missing_color(app, logged_in_client):
    _quarantine_barn()
    resp = logged_in_client.post("/batches/new", data={
        "source": "purchase", "arrival_date": "2026-08-28", "notes": "",
        "gender_0": "أنثى", "animal_no_0": "NB-05",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "لازم تحدد اللون".encode() in resp.data
    assert Animal.query.filter_by(animal_no="NB-05").first() is None
