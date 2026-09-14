"""اختبار بند التصميم "بلاطات مراح" (طلبك: "استمر حتى تغطي كل
الشاشات") — دفعة ثانية: بروتوكولات العلاج، تقويم التحصينات، الأعراض،
برامج الشياع التوأمي."""
from datetime import date, timedelta

from app.extensions import db
from app.models import Pharmacy, Symptom, TreatmentProtocol
from app.models.repro import TwinEstrusProgram
from app.models.vaccination_schedule import VaccinationSchedule
from tests.factories import make_animal, make_barn


def test_protocols_list_shows_status_chip(logged_in_client):
    p = TreatmentProtocol(name="بروتوكول اختبار", status="active")
    db.session.add(p)
    db.session.commit()

    resp = logged_in_client.get("/health/protocols")
    assert resp.status_code == 200
    assert b"protocol-status-chip" in resp.data


def test_vaccination_schedule_past_shows_status_chip(logged_in_client):
    barn = make_barn()
    pharmacy = Pharmacy(name="لقاح اختبار", available_qty=10, status="active")
    db.session.add(pharmacy)
    db.session.commit()
    sched = VaccinationSchedule(
        barn_id=barn.id, pharmacy_id=pharmacy.id,
        planned_date=date.today() - timedelta(days=5), status="completed",
    )
    db.session.add(sched)
    db.session.commit()

    resp = logged_in_client.get("/health/vaccination-schedule")
    assert resp.status_code == 200
    assert b"vax-sched-status-chip" in resp.data


def test_symptoms_list_shows_type_chip(logged_in_client):
    s = Symptom(name="عرض اختبار", is_primary=True)
    db.session.add(s)
    db.session.commit()

    resp = logged_in_client.get("/health/symptoms")
    assert resp.status_code == 200
    assert b"symptom-type-chip" in resp.data


def test_programs_list_shows_status_chip(logged_in_client):
    barn = make_barn()
    ewe = make_animal(animal_no="E-01", gender="أنثى", barn_id=barn.id)
    program = TwinEstrusProgram(ewe_id=ewe.id, start_date=date.today(), status="active")
    db.session.add(program)
    db.session.commit()

    resp = logged_in_client.get("/repro/programs")
    assert resp.status_code == 200
    assert b"program-status-chip" in resp.data
