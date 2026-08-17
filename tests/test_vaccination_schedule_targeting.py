"""بند إضافي 210 — طلبك: "إذا اخترت حظيرة تطلع لي أرقام المتواجدين
داخلها، أختار اللي أحتاج أحصّنه ولي ما أحتاجه ما أحط عليه علامة، لو
حبيت الكل أضغط زر 'الكل'". قبل هذا البند `VaccinationSchedule` كانت
دايماً تستهدف الحظيرة كاملة بدون أي خيار تحديد رؤوس معيّنة."""
from datetime import date, timedelta

from app.extensions import db
from app.models import VaccinationSchedule
from factories import make_animal, make_barn, make_pharmacy


def test_new_schedule_with_no_selected_animals_targets_whole_barn(app, logged_in_client):
    barn = make_barn(barn_no="VST-01")
    make_animal(animal_no="VST-01-A1", barn_id=barn.id)
    make_animal(animal_no="VST-01-A2", barn_id=barn.id)
    vaccine = make_pharmacy(name="لقاح استهداف1", medicine_class="vaccine")

    resp = logged_in_client.post("/health/vaccination-schedule/new", data={
        "barn_id": str(barn.id), "pharmacy_id": str(vaccine.id),
        "planned_date": (date.today() + timedelta(days=7)).isoformat(),
    }, follow_redirects=True)
    assert resp.status_code == 200

    schedule = VaccinationSchedule.query.one()
    assert schedule.target_animal_ids is None
    assert schedule.target_count() == 2
    assert {a.animal_no for a in schedule.target_animals()} == {"VST-01-A1", "VST-01-A2"}


def test_new_schedule_with_specific_animals_targets_only_those(app, logged_in_client):
    barn = make_barn(barn_no="VST-02")
    a1 = make_animal(animal_no="VST-02-A1", barn_id=barn.id)
    make_animal(animal_no="VST-02-A2", barn_id=barn.id)
    vaccine = make_pharmacy(name="لقاح استهداف2", medicine_class="vaccine")

    resp = logged_in_client.post("/health/vaccination-schedule/new", data={
        "barn_id": str(barn.id), "pharmacy_id": str(vaccine.id),
        "planned_date": (date.today() + timedelta(days=7)).isoformat(),
        "animal_ids": [str(a1.id)],
    }, follow_redirects=True)
    assert resp.status_code == 200

    schedule = VaccinationSchedule.query.one()
    assert schedule.target_animal_ids == str(a1.id)
    assert schedule.target_count() == 1
    assert [a.animal_no for a in schedule.target_animals()] == ["VST-02-A1"]


def test_form_embeds_barn_animals_for_client_side_checklist(app, logged_in_client):
    barn = make_barn(barn_no="VST-03")
    make_animal(animal_no="VST-03-A1", barn_id=barn.id)
    resp = logged_in_client.get("/health/vaccination-schedule/new")
    body = resp.data.decode()
    assert "VST-03-A1" in body
    assert 'name="animal_ids"' not in body  # يُبنى ديناميكياً بالجافاسكربت، مو ثابتاً بالـHTML
    assert "selectAllBtn" in body
