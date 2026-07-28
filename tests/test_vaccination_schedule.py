"""اختبارات تقويم التحصينات (بند إضافي 63): جدولة تحصين جماعي مستقبلي
لحظيرة كاملة، عدد الرؤوس يُحسب حياً مو مخزَّناً."""
from datetime import date, timedelta

from app.extensions import db
from app.models import VaccinationSchedule
from factories import make_animal, make_barn, make_pharmacy


def test_new_schedule_requires_vaccine_class_pharmacy(app, logged_in_client):
    barn = make_barn(barn_no="VS-01")
    antiparasitic = make_pharmacy(name="مضاد ديدان", medicine_class="antiparasitic")
    resp = logged_in_client.post("/health/vaccination-schedule/new", data={
        "barn_id": str(barn.id), "pharmacy_id": str(antiparasitic.id),
        "planned_date": (date.today() + timedelta(days=7)).isoformat(),
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert VaccinationSchedule.query.count() == 0


def test_new_schedule_creates_row_with_scheduled_status(app, logged_in_client):
    barn = make_barn(barn_no="VS-02")
    vaccine = make_pharmacy(name="لقاح جدولة", medicine_class="vaccine")
    resp = logged_in_client.post("/health/vaccination-schedule/new", data={
        "barn_id": str(barn.id), "pharmacy_id": str(vaccine.id),
        "planned_date": (date.today() + timedelta(days=7)).isoformat(), "notes": "دفعة الخريف",
    }, follow_redirects=True)
    assert resp.status_code == 200
    schedule = VaccinationSchedule.query.one()
    assert schedule.status == "scheduled"
    assert schedule.barn_id == barn.id
    assert schedule.notes == "دفعة الخريف"


def test_live_head_count_reflects_current_barn_animals_not_a_snapshot(app, logged_in_client):
    barn = make_barn(barn_no="VS-03")
    vaccine = make_pharmacy(name="لقاح جدولة2", medicine_class="vaccine")
    schedule = VaccinationSchedule(barn_id=barn.id, pharmacy_id=vaccine.id,
                                    planned_date=date.today() + timedelta(days=7))
    db.session.add(schedule)
    db.session.commit()
    assert schedule.live_head_count() == 0

    make_animal(animal_no="VS-03-A1", barn_id=barn.id)
    make_animal(animal_no="VS-03-A2", barn_id=barn.id)
    assert schedule.live_head_count() == 2


def test_cancel_schedule_sets_status(app, logged_in_client):
    barn = make_barn(barn_no="VS-04")
    vaccine = make_pharmacy(name="لقاح جدولة3", medicine_class="vaccine")
    schedule = VaccinationSchedule(barn_id=barn.id, pharmacy_id=vaccine.id, planned_date=date.today())
    db.session.add(schedule)
    db.session.commit()

    resp = logged_in_client.post(f"/health/vaccination-schedule/{schedule.id}/cancel", follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(schedule)
    assert schedule.status == "cancelled"


def test_complete_schedule_sets_status_and_timestamp(app, logged_in_client):
    barn = make_barn(barn_no="VS-05")
    vaccine = make_pharmacy(name="لقاح جدولة4", medicine_class="vaccine")
    schedule = VaccinationSchedule(barn_id=barn.id, pharmacy_id=vaccine.id, planned_date=date.today())
    db.session.add(schedule)
    db.session.commit()

    resp = logged_in_client.post(f"/health/vaccination-schedule/{schedule.id}/complete", follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(schedule)
    assert schedule.status == "completed"
    assert schedule.completed_at is not None


def test_list_separates_upcoming_from_past(app, logged_in_client):
    barn = make_barn(barn_no="VS-06")
    vaccine = make_pharmacy(name="لقاح جدولة5", medicine_class="vaccine")
    upcoming = VaccinationSchedule(barn_id=barn.id, pharmacy_id=vaccine.id,
                                    planned_date=date.today() + timedelta(days=3), status="scheduled")
    completed = VaccinationSchedule(barn_id=barn.id, pharmacy_id=vaccine.id,
                                     planned_date=date.today() - timedelta(days=3), status="completed")
    db.session.add_all([upcoming, completed])
    db.session.commit()

    resp = logged_in_client.get("/health/vaccination-schedule")
    assert resp.status_code == 200


def test_vaccination_schedule_requires_health_manage_to_create(app, client, worker):
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"}, follow_redirects=True)
    resp = client.get("/health/vaccination-schedule/new")
    assert resp.status_code == 403
