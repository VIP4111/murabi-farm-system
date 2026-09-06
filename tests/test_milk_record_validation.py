"""فحص "أكواد الحيوانات" — سجل الوزن (`add_weight_record`) والسعر عندهما
فحص منطقي قبل الحفظ (`validation_service.validate_weight`/`validate_price`)،
لكن سجل الحليب (`add_milk_record`) ما عنده أي فحص إطلاقاً — كمية سالبة
أو صفرية أو خطأ كتابة واضح (250 بدل 2.5 مثلاً) كانت تُحفظ بصمت، تلوّث
تقارير إنتاج الحليب وتنبيهات فترة السحب."""
from datetime import date, timedelta

import pytest

from app.core.animal_service import add_milk_record
from tests.factories import make_animal


def test_negative_milk_quantity_is_rejected(app):
    with app.app_context():
        animal = make_animal(animal_no="TIP-MILK-1")
        with pytest.raises(ValueError, match="موجباً"):
            add_milk_record(animal=animal, record_date=date.today(), session="صباح", quantity_liters=-1)


def test_absurdly_large_milk_quantity_is_rejected(app):
    with app.app_context():
        animal = make_animal(animal_no="TIP-MILK-2")
        with pytest.raises(ValueError, match="غير منطقية"):
            add_milk_record(animal=animal, record_date=date.today(), session="صباح", quantity_liters=250)


def test_future_dated_milk_record_is_rejected(app):
    with app.app_context():
        animal = make_animal(animal_no="TIP-MILK-3")
        with pytest.raises(ValueError, match="المستقبل"):
            add_milk_record(
                animal=animal, record_date=date.today() + timedelta(days=1),
                session="صباح", quantity_liters=2.5,
            )


def test_normal_milk_quantity_is_accepted(app):
    with app.app_context():
        animal = make_animal(animal_no="TIP-MILK-4")
        row = add_milk_record(animal=animal, record_date=date.today(), session="مساء", quantity_liters=2.5)
        assert row.quantity_liters == 2.5


def test_milk_route_shows_friendly_error_not_500(app, logged_in_client):
    with app.app_context():
        animal = make_animal(animal_no="TIP-MILK-5")
        animal_id = animal.id

    resp = logged_in_client.post(f"/animals/{animal_id}/milk/new", data={
        "date": date.today().isoformat(), "session": "صباح", "quantity_liters": "-3",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "موجباً" in resp.data.decode()
