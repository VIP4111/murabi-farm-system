"""اختبارات app/core/animal_service.py — التركيز على بند إضافي 46 (١):
الرقم المؤقت TEMP-ID ومعالجة سهو التواريخ."""
from datetime import date

import pytest

from app.core.animal_service import create_animal, generate_temp_animal_no
from app.models.animal import AnimalSource
from factories import make_animal


def test_birth_without_mother_rejected(app):
    with pytest.raises(ValueError):
        create_animal(animal_no="X-01", source=AnimalSource.BIRTH, gender="أنثى")


def test_purchase_without_animal_no_rejected(app):
    """الرقم المؤقت التلقائي مقصور على المواليد المربوطة بأم — أي مصدر
    ثاني (شراء/هدية/رصيد افتتاحي) لازم رقم صريح."""
    with pytest.raises(ValueError):
        create_animal(animal_no=None, source=AnimalSource.PURCHASE, gender="ذكر")


def test_birth_generates_temp_id_when_no_number_given(app):
    mother = make_animal(animal_no="MOM-01", gender="أنثى")
    newborn = create_animal(animal_no=None, source=AnimalSource.BIRTH, gender="أنثى", mother_id=mother.id)
    assert newborn.animal_no == "TEMP-MOM-01-1"


def test_temp_id_increments_for_twins(app):
    mother = make_animal(animal_no="MOM-02", gender="أنثى")
    first = create_animal(animal_no=None, source=AnimalSource.BIRTH, gender="ذكر", mother_id=mother.id)
    second = create_animal(animal_no=None, source=AnimalSource.BIRTH, gender="أنثى", mother_id=mother.id)
    assert first.animal_no == "TEMP-MOM-02-1"
    assert second.animal_no == "TEMP-MOM-02-2"


def test_generate_temp_animal_no_directly(app):
    mother = make_animal(animal_no="MOM-03", gender="أنثى")
    assert generate_temp_animal_no(mother) == "TEMP-MOM-03-1"


def test_birth_date_defaults_to_today_when_omitted(app):
    """قبل بند 46 كان `birth_date` يبقى None لو نُسي — صار يُفترض اليوم
    تلقائياً، نفس نمط purchase_date/entry_date الموجود من قبل."""
    mother = make_animal(animal_no="MOM-04", gender="أنثى")
    newborn = create_animal(animal_no="LAMB-01", source=AnimalSource.BIRTH, gender="ذكر", mother_id=mother.id)
    assert newborn.birth_date == date.today()


def test_purchase_date_defaults_to_today_when_omitted(app):
    animal = create_animal(animal_no="P-01", source=AnimalSource.PURCHASE, gender="ذكر")
    assert animal.purchase_date == date.today()


def test_gift_entry_date_defaults_to_today_when_omitted(app):
    animal = create_animal(animal_no="G-01", source=AnimalSource.GIFT, gender="أنثى")
    assert animal.entry_date == date.today()


def test_purchase_with_price_creates_finance_row(app):
    from app.models import Finance
    animal = create_animal(animal_no="P-02", source=AnimalSource.PURCHASE, gender="ذكر", price=500)
    rows = Finance.query.filter_by(related_animal_id=animal.id).all()
    assert len(rows) == 1
    assert rows[0].operation_type == "purchase"
    assert rows[0].amount == 500


def test_gift_does_not_create_finance_row(app):
    from app.models import Finance
    animal = create_animal(animal_no="G-02", source=AnimalSource.GIFT, gender="أنثى", price=500)
    assert Finance.query.filter_by(related_animal_id=animal.id).count() == 0
