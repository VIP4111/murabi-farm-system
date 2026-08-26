"""بند إضافي 236 — بند 2 من خطة الأتمتة الواقعية: كشف حمل ضمني. لو
تقريع مسجَّل مرّ عليه estrus_return_window_days بدون ما ترجع الأنثى
للفحل، هذا مؤشر حمل قوي — نسجّل حمل غير مؤكَّد ونجدول فحص سونار."""
from datetime import date, timedelta

from app.extensions import db
from app.core import pregnancy_care_service
from app.models import Mating, Pregnancy, Task, FarmSettings
from tests.factories import make_animal, make_barn


def _mating(female, male=None, days_ago=25):
    m = Mating(female_id=female.id, male_id=male.id if male else None,
                date=date.today() - timedelta(days=days_ago))
    db.session.add(m)
    db.session.commit()
    return m


def test_no_return_mating_creates_implicit_pregnancy(app):
    female = make_animal(animal_no="EWE-236-01", gender="أنثى")
    male = make_animal(animal_no="RAM-236-01", gender="ذكر")
    mating = _mating(female, male, days_ago=25)

    created = pregnancy_care_service.detect_implicit_pregnancies()
    assert len(created) == 1
    assert created[0].mating_id == mating.id
    assert created[0].confirmed is False

    task = Task.query.filter_by(source_type="ImplicitPregnancy", source_id=mating.id).first()
    assert task is not None
    assert task.animal_id == female.id
    assert task.due_date == mating.date + timedelta(days=FarmSettings.get().implicit_pregnancy_sonar_check_days)


def test_too_recent_mating_not_flagged_yet(app):
    female = make_animal(animal_no="EWE-236-02", gender="أنثى")
    _mating(female, days_ago=5)
    created = pregnancy_care_service.detect_implicit_pregnancies()
    assert created == []


def test_returning_to_mating_cancels_implicit_pregnancy(app):
    female = make_animal(animal_no="EWE-236-03", gender="أنثى")
    first = _mating(female, days_ago=40)
    second = _mating(female, days_ago=22)  # رجعت للفحل بعد 18 يوم — داخل نافذة 21 يوم
    created = pregnancy_care_service.detect_implicit_pregnancies()
    # التقريع الأول ما يُعتبر (رجعت للفحل)، الثاني نفسه صار آخر تقريع
    # بلا رجوع، فهو المرشَّح الصحيح الآن.
    assert [p.mating_id for p in created] == [second.id]
    assert first.id not in [p.mating_id for p in created]


def test_idempotent_no_duplicate_on_second_call(app):
    female = make_animal(animal_no="EWE-236-04", gender="أنثى")
    _mating(female, days_ago=25)
    pregnancy_care_service.detect_implicit_pregnancies()
    second = pregnancy_care_service.detect_implicit_pregnancies()
    assert second == []
    assert Pregnancy.query.count() == 1


def test_manual_pregnancy_already_linked_skips_detection(app):
    female = make_animal(animal_no="EWE-236-05", gender="أنثى")
    mating = _mating(female, days_ago=25)
    db.session.add(Pregnancy(female_id=female.id, mating_id=mating.id, date=mating.date, confirmed=True))
    db.session.commit()

    created = pregnancy_care_service.detect_implicit_pregnancies()
    assert created == []
    assert Pregnancy.query.count() == 1


def test_birth_already_recorded_skips_detection(app):
    female = make_animal(animal_no="EWE-236-06", gender="أنثى")
    mating = _mating(female, days_ago=100)
    from app.models.animal import AnimalSource
    newborn = make_animal(animal_no="LAMB-236-06", gender="أنثى", source=AnimalSource.BIRTH)
    newborn.mother_id = female.id
    newborn.birth_date = mating.date + timedelta(days=50)
    db.session.commit()

    created = pregnancy_care_service.detect_implicit_pregnancies()
    assert created == []


def test_does_not_mark_female_as_confirmed_pregnant(app):
    """حمل غير مؤكَّد ما يفترض يؤثّر على فلاتر الجاهزية للتقريع —
    نفس سلوك نعجة حامل عند الشراء بالضبط."""
    female = make_animal(animal_no="EWE-236-07", gender="أنثى")
    _mating(female, days_ago=25)
    pregnancy_care_service.detect_implicit_pregnancies()

    from app.core.animal_filters_service import _is_currently_pregnant
    assert _is_currently_pregnant(female) is False
