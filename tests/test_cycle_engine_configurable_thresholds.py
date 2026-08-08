"""بند إضافي 153 — طلبك: "نُبقي البوابات كود، ونخلي الأرقام بس قابلة
للتعديل من الإعدادات". قبل هذا البند، أعمار محرك دورة الإنتاج
(مولود/فحص خصوبة/فطام) كانت أرقاماً ثابتة بالكود (`cycle_engine.py`)
بدون أي شاشة تعديل — صارت الآن حقول بـ`FarmSettings`، ومنطق البوابة
نفسه (أي دليل مطلوب) باقٍ كود زي ما هو."""
from datetime import date, timedelta

from app.core import cycle_engine
from app.extensions import db
from app.models import FarmSettings
from factories import make_animal
from app.models.animal import AnimalSource


def test_newborn_route_respects_configured_max_age(app):
    fs = FarmSettings.get()
    fs.newborn_route_max_age_days = 10
    db.session.commit()

    animal = make_animal(animal_no="THR-01", source=AnimalSource.BIRTH)
    animal.birth_date = date.today() - timedelta(days=20)
    db.session.commit()

    assert cycle_engine.determine_route(animal) != "newborn"


def test_weaning_gate_respects_configured_min_age(app):
    fs = FarmSettings.get()
    fs.weaning_min_age_days = 5
    fs.weaning_alt_age_days = 8
    db.session.commit()

    animal = make_animal(animal_no="THR-02", source=AnimalSource.BIRTH, gender="ذكر")
    animal.birth_date = date.today() - timedelta(days=6)
    animal.purpose = "تربية"
    db.session.commit()
    wf = cycle_engine.get_or_create_workflow(animal)
    wf.route = "basic_holding"
    db.session.commit()

    passed, missing = cycle_engine._gate_lactation_weaning(animal, wf)
    assert not any("عمر 5" in m or "عمر 60" in m for m in missing) or passed


def test_male_fertility_alt_age_respects_settings(app):
    fs = FarmSettings.get()
    fs.male_fertility_exam_alt_age_days = 30
    db.session.commit()

    animal = make_animal(animal_no="THR-03", gender="ذكر")
    animal.birth_date = date.today() - timedelta(days=40)
    animal.purpose = "تربية"
    db.session.commit()
    wf = cycle_engine.get_or_create_workflow(animal)
    wf.route = "male_breeder"
    db.session.commit()

    passed, missing = cycle_engine._gate_breeding_prep(animal, wf)
    assert not any("فحص خصوبة" in m for m in missing)
