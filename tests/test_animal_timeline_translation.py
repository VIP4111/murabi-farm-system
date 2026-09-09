"""بند إصلاح (فحص عميق — طلبك: "ابدأ فحص عميق لباقي الشاشات") —
التسلسل الزمني بصفحة تفاصيل الرأس (`animal_profile_service.py`) كان
عربي بحت بدون أي `_()` (لا استيراد gettext أصلاً بهذا الملف) — كل
بند (زيارة بيطرية، مرض، تحصين، وزن، حليب، ولادة، مالية، تقريع، تشخيص
حمل، فحص سونار) عربي دايماً بغض النظر عن لغة الحساب."""
from datetime import date

from app.extensions import db
from app.core import animal_profile_service
from app.models import Vaccination
from tests.factories import make_animal
from flask_babel import force_locale


def test_age_label_translates_to_english(app):
    animal = make_animal(animal_no="EN-TL-1")
    animal.birth_date = date(2026, 1, 1)
    db.session.commit()
    with force_locale("en"):
        label = animal_profile_service._age_label(animal.birth_date)
    assert "day" in label or "month" in label or "year" in label
    assert "يوم" not in label and "شهر" not in label and "سنة" not in label


def test_timeline_category_translates_to_english(app):
    animal = make_animal(animal_no="EN-TL-2")
    db.session.add(Vaccination(animal_id=animal.id, vaccine_name="CDT", date=date(2026, 1, 1)))
    db.session.commit()
    with force_locale("en"):
        profile = animal_profile_service.get_profile(animal)
    categories = [e["category"] for e in profile["timeline"]]
    assert "Vaccination" in categories
    assert "تحصين" not in categories
