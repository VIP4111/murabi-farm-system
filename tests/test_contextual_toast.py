"""تنبيه سياقي فوري بعد تسجيل تطعيم (بند إضافي 230) —
Contextual Triggered Notifications: تسجيل تطعيم لرأس بحظيرة فيها موعد
مجدول قريب بجدول التحصينات لازم يطلع Toast يوجّه لصفحة الجدول، وما
يطلع شي لو ما فيه موعد قريب."""
from datetime import date, timedelta

from app.extensions import db
from app.models import VaccinationSchedule
from app.core.alerts_service import vaccination_followup_toast
from tests.factories import make_animal, make_barn, make_pharmacy


def _schedule(barn_id, pharmacy_id, planned_date, status="scheduled"):
    sched = VaccinationSchedule(barn_id=barn_id, pharmacy_id=pharmacy_id,
                                 planned_date=planned_date, status=status)
    db.session.add(sched)
    db.session.commit()
    return sched


def test_toast_fires_when_schedule_due_soon(app):
    barn = make_barn()
    animal = make_animal(barn_id=barn.id)
    pharmacy = make_pharmacy()
    _schedule(barn.id, pharmacy.id, date.today() + timedelta(days=2))

    payload = vaccination_followup_toast(animal.id)
    assert payload is not None
    assert "جدول التحصينات" in payload["button_text"]
    assert payload["url_endpoint"] == "health.vaccination_schedule_list"


def test_toast_silent_when_no_schedule_due(app):
    barn = make_barn()
    animal = make_animal(barn_id=barn.id)
    assert vaccination_followup_toast(animal.id) is None


def test_toast_silent_when_schedule_far_out(app):
    barn = make_barn()
    animal = make_animal(barn_id=barn.id)
    pharmacy = make_pharmacy()
    _schedule(barn.id, pharmacy.id, date.today() + timedelta(days=30))
    assert vaccination_followup_toast(animal.id) is None


def test_toast_silent_when_schedule_already_completed(app):
    barn = make_barn()
    animal = make_animal(barn_id=barn.id)
    pharmacy = make_pharmacy()
    _schedule(barn.id, pharmacy.id, date.today() + timedelta(days=1), status="completed")
    assert vaccination_followup_toast(animal.id) is None


def test_vaccination_route_renders_toast_in_response(app, logged_in_client):
    barn = make_barn()
    animal = make_animal(barn_id=barn.id)
    pharmacy = make_pharmacy()
    _schedule(barn.id, pharmacy.id, date.today() + timedelta(days=2))

    resp = logged_in_client.post("/health/vaccinations/new", data={
        "animal_id": str(animal.id), "vaccine_name": "اختبار توست",
        "date": date.today().isoformat(),
    }, follow_redirects=True)
    assert resp.status_code == 200
    body = resp.data.decode()
    assert 'toast-wrap' in body
    assert 'جدول التحصينات' in body
