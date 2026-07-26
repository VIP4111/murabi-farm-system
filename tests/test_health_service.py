"""اختبارات app/health/health_service.py — بند إضافي 46 (٢): حظر السحب
بالسالب من الصيدلية + حساب فترة السحب/التحريم."""
from datetime import date, timedelta

import pytest

from app.health import health_service
from factories import make_animal, make_pharmacy


def test_deduct_stock_raises_when_insufficient(app):
    pharmacy = make_pharmacy(name="دواء أ", available_qty=5)
    with pytest.raises(ValueError):
        pharmacy.deduct_stock(20)
    assert pharmacy.available_qty == 5, "stock must stay untouched on rejection"


def test_deduct_stock_succeeds_within_available(app):
    pharmacy = make_pharmacy(name="دواء ب", available_qty=5)
    pharmacy.deduct_stock(3)
    assert pharmacy.available_qty == 2


def test_record_vaccination_with_insufficient_stock_raises_incomplete_record_error(app):
    animal = make_animal(animal_no="V-01")
    pharmacy = make_pharmacy(name="دواء ج", available_qty=2, withdrawal_days=5)
    with pytest.raises(health_service.IncompleteRecordError):
        health_service.record_vaccination(
            actor_user_id=1, animal_id=animal.id, vaccine_name="لقاح اختبار",
            date_=date.today(), pharmacy_id=pharmacy.id, quantity_used=10,
        )
    assert pharmacy.available_qty == 2, "no partial deduction on rejection"


def test_record_vaccination_success_sets_withdrawal_period(app):
    animal = make_animal(animal_no="V-02")
    pharmacy = make_pharmacy(name="دواء د", available_qty=10, withdrawal_days=5, unit_price=2)
    health_service.record_vaccination(
        actor_user_id=1, animal_id=animal.id, vaccine_name="لقاح اختبار",
        date_=date.today(), pharmacy_id=pharmacy.id, quantity_used=3,
    )
    assert pharmacy.available_qty == 7
    until = health_service.animal_under_withdrawal(animal.id)
    assert until == date.today() + timedelta(days=5)


def test_medicine_without_quantity_raises_incomplete_record_error(app):
    animal = make_animal(animal_no="V-03")
    pharmacy = make_pharmacy(name="دواء هـ", available_qty=10)
    with pytest.raises(health_service.IncompleteRecordError):
        health_service.record_vaccination(
            actor_user_id=1, animal_id=animal.id, vaccine_name="لقاح اختبار",
            date_=date.today(), pharmacy_id=pharmacy.id, quantity_used=None,
        )


def test_cost_computed_automatically_from_unit_price(app):
    animal = make_animal(animal_no="V-04")
    pharmacy = make_pharmacy(name="دواء و", available_qty=10, unit_price=4)
    disease = health_service.record_disease(
        actor_user_id=1, animal_id=animal.id, disease_name="مرض اختبار",
        date_=date.today(), severity="light", pharmacy_id=pharmacy.id, quantity_used=2,
    )
    assert disease.treatment_cost == 8
