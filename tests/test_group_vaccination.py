"""اختبارات تحصين جماعي بلقاحين + جرعة حسب العمر (بند إضافي 60):
- `PharmacyDoseRule.find_dose` مطابقة نطاق عمري بلا حساب/اختراع رقم.
- `/health/pharmacy/<id>/dose-rules` نقطة JSON تُغذّي شاشة التحصين الجماعي.
- `apply_bulk_vaccination` بمخرجات لقاحين، موعد قادم تلقائي من protection_days،
  وحركة Finance واحدة لكل لقاح بإجمالي تكلفة رؤوسه.
- مربع التأشير لكل رأس/لكل لقاح يحدد فعلياً مين انحصّن — تخطّي رأس غير
  مؤشَّر عليه لا يمنع بقية الدفعة.
"""
from datetime import date, timedelta

from app.core import bulk_service
from app.extensions import db
from app.models import Finance, Pharmacy, PharmacyDoseRule, Vaccination
from factories import make_animal, make_pharmacy


def _vaccine_with_protection(name, protection_days):
    item = Pharmacy(name=name, available_qty=100, unit_price=5, medicine_class="vaccine",
                     status="active", protection_days=protection_days)
    db.session.add(item)
    db.session.commit()
    return item


def test_find_dose_matches_correct_age_bracket(app):
    vaccine = _vaccine_with_protection("لقاح أ", None)
    db.session.add(PharmacyDoseRule(pharmacy_id=vaccine.id, age_from_days=0, age_to_days=30, dose_ml=1))
    db.session.add(PharmacyDoseRule(pharmacy_id=vaccine.id, age_from_days=31, age_to_days=90, dose_ml=2.5))
    db.session.commit()
    assert PharmacyDoseRule.find_dose(vaccine.id, 15) == 1
    assert PharmacyDoseRule.find_dose(vaccine.id, 45) == 2.5


def test_find_dose_returns_none_outside_any_bracket_or_unknown_age(app):
    vaccine = _vaccine_with_protection("لقاح أ", None)
    db.session.add(PharmacyDoseRule(pharmacy_id=vaccine.id, age_from_days=0, age_to_days=30, dose_ml=1))
    db.session.commit()
    assert PharmacyDoseRule.find_dose(vaccine.id, 999) is None
    assert PharmacyDoseRule.find_dose(vaccine.id, None) is None


def test_dose_rules_json_endpoint_returns_protection_days_and_rules(app, logged_in_client):
    vaccine = _vaccine_with_protection("لقاح أ", 21)
    db.session.add(PharmacyDoseRule(pharmacy_id=vaccine.id, age_from_days=0, age_to_days=30, dose_ml=1))
    db.session.commit()
    resp = logged_in_client.get(f"/health/pharmacy/{vaccine.id}/dose-rules")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["protection_days"] == 21
    assert data["rules"] == [{"age_from_days": 0, "age_to_days": 30, "dose_ml": 1}]


def test_apply_bulk_vaccination_computes_next_due_date_from_protection_days(app):
    a1 = make_animal(animal_no="GV-01")
    vaccine = _vaccine_with_protection("لقاح أ", 21)
    record_date = date.today()
    bulk_service.apply_bulk_vaccination(
        record_date=record_date, actor_user_id=1,
        vaccine_slots=[{"pharmacy_id": vaccine.id, "doses": {a1.id: 2}}],
    )
    vacc = Vaccination.query.filter_by(animal_id=a1.id).one()
    assert vacc.next_due_date == record_date + timedelta(days=21)


def test_apply_bulk_vaccination_creates_one_finance_expense_per_vaccine(app):
    a1 = make_animal(animal_no="GV-02")
    a2 = make_animal(animal_no="GV-03")
    vaccine = _vaccine_with_protection("لقاح أ", None)  # unit_price=5
    bulk_service.apply_bulk_vaccination(
        record_date=date.today(), actor_user_id=1,
        vaccine_slots=[{"pharmacy_id": vaccine.id, "doses": {a1.id: 2, a2.id: 3}}],
    )
    entries = Finance.query.filter_by(category="تحصين").all()
    assert len(entries) == 1
    assert entries[0].amount == 25  # (2*5) + (3*5)
    assert entries[0].operation_type == "expense"


def test_apply_bulk_vaccination_two_slots_create_two_records_per_animal_with_own_dose(app):
    a1 = make_animal(animal_no="GV-04")
    vaccine1 = _vaccine_with_protection("سلينيوم", None)
    vaccine2 = _vaccine_with_protection("تحصين دود الكبد", None)
    results = bulk_service.apply_bulk_vaccination(
        record_date=date.today(), actor_user_id=1,
        vaccine_slots=[
            {"pharmacy_id": vaccine1.id, "doses": {a1.id: 1.5}},
            {"pharmacy_id": vaccine2.id, "doses": {a1.id: 3}},
        ],
    )
    assert results[(vaccine1.id, a1.id)] == "تم"
    assert results[(vaccine2.id, a1.id)] == "تم"
    records = Vaccination.query.filter_by(animal_id=a1.id).order_by(Vaccination.vaccine_name).all()
    assert len(records) == 2
    by_name = {r.vaccine_name: r.quantity_used for r in records}
    assert by_name["سلينيوم"] == 1.5
    assert by_name["تحصين دود الكبد"] == 3


def test_apply_bulk_vaccination_unchecked_animal_gets_no_record(app):
    """رأس ما انحطّ بمربع تأشيره ضمن `doses` أصلاً — نفس سلوك مربع
    "طعّمت" بشاشة التحصين الجماعي (بند 60): ما ينحصّن به إطلاقاً."""
    a1 = make_animal(animal_no="GV-05")
    a2 = make_animal(animal_no="GV-06")
    vaccine = _vaccine_with_protection("لقاح أ", None)
    bulk_service.apply_bulk_vaccination(
        record_date=date.today(), actor_user_id=1,
        vaccine_slots=[{"pharmacy_id": vaccine.id, "doses": {a1.id: 1}}],
    )
    assert Vaccination.query.filter_by(animal_id=a1.id).count() == 1
    assert Vaccination.query.filter_by(animal_id=a2.id).count() == 0


def test_bulk_apply_route_rejects_non_vaccine_pharmacy(app, logged_in_client):
    a1 = make_animal(animal_no="GV-07")
    antiparasitic = make_pharmacy(name="مضاد ديدان", available_qty=10, medicine_class="antiparasitic")
    resp = logged_in_client.post("/animals/bulk/apply/vaccination", data={
        "animal_ids": [str(a1.id)], "date": date.today().isoformat(),
        "vaccine_1_pharmacy_id": str(antiparasitic.id),
        f"vaccinated_1_{a1.id}": "1", f"dose_1_{a1.id}": "2",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert Vaccination.query.filter_by(animal_id=a1.id).count() == 0


def test_bulk_apply_route_registers_only_checked_animal(app, logged_in_client):
    a1 = make_animal(animal_no="GV-08")
    a2 = make_animal(animal_no="GV-09")
    vaccine = _vaccine_with_protection("لقاح أ", None)
    resp = logged_in_client.post("/animals/bulk/apply/vaccination", data={
        "animal_ids": [str(a1.id), str(a2.id)], "date": date.today().isoformat(),
        "vaccine_1_pharmacy_id": str(vaccine.id),
        f"vaccinated_1_{a1.id}": "1", f"dose_1_{a1.id}": "2",
        # a2 ما تؤشر عليه إطلاقاً
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert Vaccination.query.filter_by(animal_id=a1.id).count() == 1
    assert Vaccination.query.filter_by(animal_id=a2.id).count() == 0
