"""فحص عميق — قسم النعام: `record_hatch_success`/`record_hatch_failure`
ما كان عندهما أي حارس ضد تسجيل نتيجة فقس على بيضة مسجَّلة لها نتيجة
أصلاً. إعادة إرسال الفورم بالغلط (رجوع بالمتصفح، ضغطة مزدوجة) كانت
تنشئ رأساً ثانياً مكرَّراً لنفس البيضة الفعلية، أو تكتب فوق سبب الفشل
الأصلي بصمت — نفس مبدأ الحارس الموجود أصلاً بـ`pregnancies_abort`."""
import pytest
from datetime import date

from app.extensions import db
from app.core import ostrich_service as svc
from app.models import Animal
from app.models.animal import AnimalSource
from app.models.ostrich import OstrichEgg


def _egg():
    mother = Animal(animal_no="OST-M-01", source=AnimalSource.PURCHASE, gender="أنثى",
                     species="ostrich", status="active")
    db.session.add(mother)
    db.session.commit()
    egg = OstrichEgg(mother_id=mother.id, lay_date=date.today())
    db.session.add(egg)
    db.session.commit()
    return egg


def test_double_hatch_success_rejected_no_duplicate_animal(app):
    egg = _egg()
    svc.record_hatch_success(egg, actual_hatch_date=date.today(), animal_no="OST-C-01")
    animals_before = Animal.query.filter_by(species="ostrich", gender=None).count()

    with pytest.raises(svc.OstrichEggAlreadyProcessedError):
        svc.record_hatch_success(egg, actual_hatch_date=date.today(), animal_no="OST-C-02")

    animals_after = Animal.query.filter_by(species="ostrich", gender=None).count()
    assert animals_after == animals_before, "رأس ثانٍ انسجّل لنفس البيضة رغم إنها مسجَّلة فقس من قبل"


def test_hatch_failure_does_not_overwrite_existing_result(app):
    egg = _egg()
    svc.record_hatch_failure(egg, fail_reason="سبب أصلي")

    with pytest.raises(svc.OstrichEggAlreadyProcessedError):
        svc.record_hatch_failure(egg, fail_reason="سبب مكرَّر بالغلط")

    db.session.refresh(egg)
    assert egg.fail_reason == "سبب أصلي"


def test_success_after_failure_rejected(app):
    egg = _egg()
    svc.record_hatch_failure(egg, fail_reason="فشل حقيقي")

    with pytest.raises(svc.OstrichEggAlreadyProcessedError):
        svc.record_hatch_success(egg, actual_hatch_date=date.today(), animal_no="OST-C-03")
