"""بند إضافي 283 — سؤالك الصريح: "هل الرش متوفر بالمستودع؟ هل يقترح
نوع الرش؟" بنسبة للتحصين نفس الشي. قبل هذا البند، مهمتي "رش وقائي"/
"تحصين مبدئي" عند شراء رأس ودخوله حظيرة العزل كانتا تذكير عام بدون أي
ربط بصنف صيدلية فعلي. صارت تُربط بدواء افتراضي تحدده من الإعدادات."""
from datetime import date

from app.extensions import db
from app.core.animal_service import create_animal
from app.models.animal import AnimalSource
from app.models import FarmSettings, Task
from factories import make_barn, make_pharmacy


def _quarantine_barn():
    return make_barn(barn_no="Q-283", barn_type="عزل")


def test_no_default_medicine_configured_tasks_stay_plain_reminders(app):
    barn = _quarantine_barn()
    animal = create_animal(animal_no="IM-01", source=AnimalSource.PURCHASE, gender="أنثى", barn_id=barn.id)
    spray_task = Task.query.filter_by(task_type="batch_spray", animal_id=animal.id).first()
    vaccine_task = Task.query.filter_by(task_type="batch_initial_vaccination", animal_id=animal.id).first()
    assert spray_task.planned_pharmacy_id is None
    assert vaccine_task.planned_pharmacy_id is None


def test_default_spray_medicine_linked_to_task(app):
    spray = make_pharmacy(name="رشة اختبار ضد الطفيليات", available_qty=50)
    fs = FarmSettings.get()
    fs.default_intake_spray_pharmacy_id = spray.id
    db.session.commit()

    barn = _quarantine_barn()
    animal = create_animal(animal_no="IM-02", source=AnimalSource.PURCHASE, gender="أنثى", barn_id=barn.id)
    spray_task = Task.query.filter_by(task_type="batch_spray", animal_id=animal.id).first()
    assert spray_task.planned_pharmacy_id == spray.id
    assert spray_task.planned_treatment_kind == "vet_visit"
    assert spray.name in spray_task.notes


def test_default_vaccine_linked_to_task(app):
    vaccine = make_pharmacy(name="لقاح اختبار مبدئي", available_qty=30)
    fs = FarmSettings.get()
    fs.default_intake_vaccine_pharmacy_id = vaccine.id
    db.session.commit()

    barn = _quarantine_barn()
    animal = create_animal(animal_no="IM-03", source=AnimalSource.PURCHASE, gender="أنثى", barn_id=barn.id)
    vaccine_task = Task.query.filter_by(task_type="batch_initial_vaccination", animal_id=animal.id).first()
    assert vaccine_task.planned_pharmacy_id == vaccine.id
    assert vaccine_task.planned_treatment_kind == "vaccination"


def test_linked_task_shows_confirm_execution_button(app, logged_in_client):
    spray = make_pharmacy(name="رشة زر التنفيذ", available_qty=50)
    fs = FarmSettings.get()
    fs.default_intake_spray_pharmacy_id = spray.id
    db.session.commit()

    barn = _quarantine_barn()
    animal = create_animal(animal_no="IM-04", source=AnimalSource.PURCHASE, gender="أنثى", barn_id=barn.id)
    spray_task = Task.query.filter_by(task_type="batch_spray", animal_id=animal.id).first()

    resp = logged_in_client.get(f"/team/tasks/{spray_task.id}")
    body = resp.data.decode()
    assert "تأكيد التنفيذ" in body


def test_settings_route_saves_default_medicines(app, logged_in_client):
    spray = make_pharmacy(name="رشة إعدادات")
    resp = logged_in_client.post("/settings/intake-medicine", data={
        "default_intake_spray_pharmacy_id": str(spray.id),
        "default_intake_vaccine_pharmacy_id": "",
    })
    assert resp.status_code == 302
    fs = FarmSettings.get()
    assert fs.default_intake_spray_pharmacy_id == spray.id
    assert fs.default_intake_vaccine_pharmacy_id is None
