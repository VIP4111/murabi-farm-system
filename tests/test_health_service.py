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


# ---- بند إضافي (2026-08-30) — طلبك الصريح: "عندي تحريم رضاعة الحليب
# وتحريم فترة الذبح [منفصلين]" — فترة سحب الحليب صارت مستقلة تماماً
# عن فترة سحب اللحم/الذبح، بدل حقل واحد يُستخدم للاثنين مع بعض.

def test_meat_and_milk_withdrawal_are_independent(app):
    """دواء بفترتي سحب مختلفتين — كل واحدة تُحسب وتُسترجع لحالها،
    بدون ما تتأثر بالثانية."""
    animal = make_animal(animal_no="V-WD1")
    pharmacy = make_pharmacy(name="دواء سحب مزدوج", available_qty=10,
                              withdrawal_days=10, withdrawal_days_milk=3)
    health_service.record_vaccination(
        actor_user_id=1, animal_id=animal.id, vaccine_name="لقاح اختبار",
        date_=date.today(), pharmacy_id=pharmacy.id, quantity_used=1,
    )
    meat_until = health_service.animal_under_withdrawal(animal.id)
    milk_until = health_service.animal_under_milk_withdrawal(animal.id)
    assert meat_until == date.today() + timedelta(days=10)
    assert milk_until == date.today() + timedelta(days=3)
    assert meat_until != milk_until


def test_milk_recording_route_warns_from_milk_withdrawal_not_meat(app, logged_in_client):
    """قبل هذا البند، تنبيه تسجيل الحليب كان يتحقق من فترة سحب اللحم
    بالغلط. الآن: دواء بلا فترة سحب حليب مستقلة (0) بس فترة لحم طويلة
    — ما يظهر أي تحذير عند تسجيل الحليب."""
    animal = make_animal(animal_no="V-WD3")
    pharmacy = make_pharmacy(name="دواء لحم فقط 2", available_qty=10,
                              withdrawal_days=30, withdrawal_days_milk=0)
    health_service.record_vaccination(
        actor_user_id=1, animal_id=animal.id, vaccine_name="لقاح اختبار",
        date_=date.today(), pharmacy_id=pharmacy.id, quantity_used=1,
    )
    resp = logged_in_client.post(f"/animals/{animal.id}/milk/new", data={
        "date": date.today().isoformat(), "session": "صباح", "quantity_liters": "1.5",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "تحريم حليب".encode() not in resp.data


def test_milk_recording_route_warns_when_actually_under_milk_withdrawal(app, logged_in_client):
    animal = make_animal(animal_no="V-WD4")
    pharmacy = make_pharmacy(name="دواء حليب", available_qty=10,
                              withdrawal_days=0, withdrawal_days_milk=5)
    health_service.record_vaccination(
        actor_user_id=1, animal_id=animal.id, vaccine_name="لقاح اختبار",
        date_=date.today(), pharmacy_id=pharmacy.id, quantity_used=1,
    )
    resp = logged_in_client.post(f"/animals/{animal.id}/milk/new", data={
        "date": date.today().isoformat(), "session": "صباح", "quantity_liters": "1.5",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "تحريم حليب".encode() in resp.data


def test_milk_withdrawal_zero_means_no_milk_restriction(app):
    """دواء بدون فترة سحب حليب مستقلة (0) — ما يظهر أي تحريم حليب،
    حتى لو له فترة سحب لحم طويلة."""
    animal = make_animal(animal_no="V-WD2")
    pharmacy = make_pharmacy(name="دواء لحم فقط", available_qty=10,
                              withdrawal_days=20, withdrawal_days_milk=0)
    health_service.record_vaccination(
        actor_user_id=1, animal_id=animal.id, vaccine_name="لقاح اختبار",
        date_=date.today(), pharmacy_id=pharmacy.id, quantity_used=1,
    )
    assert health_service.animal_under_withdrawal(animal.id) == date.today() + timedelta(days=20)
    assert health_service.animal_under_milk_withdrawal(animal.id) is None


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
