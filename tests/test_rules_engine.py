"""اختبارات محرك القواعد الطبية والتغذوية والعملياتية الذكي (بند إضافي
51): حظر نحاس النعيمي، رعاية الحمل المتأخر، حظر الزيادة المفاجئة
للمركزات ونسبة الكالسيوم/الفوسفور، بروتوكول الإجهاض، بروتوكول الطوارئ
(عمى مفاجئ)، تأخر الشياع، ورعاية المولود الأولية."""
from datetime import date, timedelta

import pytest

from app.extensions import db
from app.core import alerts_service
from app.core.animal_service import create_animal
from app.core.isolation_service import record_abortion
from app.core.pregnancy_care_service import generate_late_pregnancy_tasks
from app.feed import feed_service
from app.health import health_service
from app.models import FarmSettings, FeedBarnPlan, FeedRation, FeedRationItem, Pregnancy, Task
from app.models.animal import AnimalSource
from factories import make_animal, make_barn, make_feed, make_pharmacy


# ---------- حظر نحاس سلالة النعيمي ----------

def test_copper_toxicity_blocks_naimi_health_record(app):
    animal = make_animal(animal_no="CU-01", breed="نعيمي")
    pharmacy = make_pharmacy(name="مكمّل نحاسي", available_qty=10, contains_high_copper=True)
    with pytest.raises(health_service.IncompleteRecordError):
        health_service.record_vaccination(
            actor_user_id=1, animal_id=animal.id, vaccine_name="جرعة",
            date_=date.today(), pharmacy_id=pharmacy.id, quantity_used=1,
        )


def test_copper_toxicity_allows_non_naimi_animal(app):
    animal = make_animal(animal_no="CU-02", breed="عام/غير محدد")
    pharmacy = make_pharmacy(name="مكمّل نحاسي", available_qty=10, contains_high_copper=True)
    health_service.record_vaccination(
        actor_user_id=1, animal_id=animal.id, vaccine_name="جرعة",
        date_=date.today(), pharmacy_id=pharmacy.id, quantity_used=1,
    )
    assert pharmacy.available_qty == 9


def test_copper_toxicity_blocks_naimi_feed_movement_with_animal_id(app):
    barn = make_barn()
    animal = make_animal(animal_no="CU-03", breed="نعيمي", barn_id=barn.id)
    feed = make_feed(name="قالب أملاح نحاسي", available_qty=10, contains_high_copper=True)
    with pytest.raises(ValueError):
        feed_service.record_movement(
            feed=feed, movement_type="out", quantity=1, barn_id=barn.id, animal_id=animal.id,
        )


def test_copper_toxicity_allows_barn_level_feed_movement_without_animal_id(app):
    """قرارك الصريح: الحظر مقصور على سجلات مرتبطة برأس محدد — حركة
    مستوى الحظيرة بدون animal_id ما تُفحص، حتى لو الحظيرة فيها نعيمي."""
    barn = make_barn()
    make_animal(animal_no="CU-04", breed="نعيمي", barn_id=barn.id)
    feed = make_feed(name="قالب أملاح نحاسي", available_qty=10, contains_high_copper=True)
    feed_service.record_movement(feed=feed, movement_type="out", quantity=1, barn_id=barn.id)
    assert feed.available_qty == 9


# ---------- رعاية الحمل المتأخر ----------

def _confirmed_pregnancy(animal, mating_date):
    p = Pregnancy(female_id=animal.id, date=mating_date, confirmed=True)
    db.session.add(p)
    db.session.commit()
    return p


def test_late_pregnancy_task_created_when_due(app):
    animal = make_animal(animal_no="PG-01", gender="أنثى")
    fs = FarmSettings.get()
    mating_date = date.today() - timedelta(days=fs.gestation_days - fs.pre_birth_feed_change_days)
    _confirmed_pregnancy(animal, mating_date)

    created = generate_late_pregnancy_tasks()
    assert len(created) == 1
    assert created[0].animal_id == animal.id
    assert created[0].task_type == "late_pregnancy_care"


def test_late_pregnancy_task_skipped_when_not_yet_due(app):
    animal = make_animal(animal_no="PG-02", gender="أنثى")
    _confirmed_pregnancy(animal, date.today())  # حمل جديد، لسا بعيد عن الثلث الأخير
    assert generate_late_pregnancy_tasks() == []


def test_late_pregnancy_task_idempotent(app):
    animal = make_animal(animal_no="PG-03", gender="أنثى")
    fs = FarmSettings.get()
    mating_date = date.today() - timedelta(days=fs.gestation_days - fs.pre_birth_feed_change_days)
    _confirmed_pregnancy(animal, mating_date)

    first = generate_late_pregnancy_tasks()
    second = generate_late_pregnancy_tasks()
    assert len(first) == 1
    assert len(second) == 0


def test_late_pregnancy_task_skips_aborted_pregnancy(app):
    animal = make_animal(animal_no="PG-04", gender="أنثى")
    fs = FarmSettings.get()
    mating_date = date.today() - timedelta(days=fs.gestation_days - fs.pre_birth_feed_change_days)
    p = _confirmed_pregnancy(animal, mating_date)
    p.outcome = "abortion"
    db.session.commit()
    assert generate_late_pregnancy_tasks() == []


# ---------- حظر الزيادة المفاجئة للمركزات ----------

def _make_ration(name, concentrate_pct, feed_price=1.0):
    concentrate = make_feed(name=f"{name}-مركّز", feed_class="concentrate", unit_price=feed_price)
    roughage = make_feed(name=f"{name}-خشن", feed_class="roughage", unit_price=feed_price)
    ration = FeedRation(name=name)
    db.session.add(ration)
    db.session.flush()
    db.session.add(FeedRationItem(ration_id=ration.id, feed_id=concentrate.id, percent=concentrate_pct))
    db.session.add(FeedRationItem(ration_id=ration.id, feed_id=roughage.id, percent=100 - concentrate_pct))
    db.session.commit()
    db.session.expire(ration, ["items"])
    return ration


def test_concentrate_increase_warning_none_without_prior_plan(app):
    barn = make_barn()
    ration = _make_ration("و1", 50)
    fs = FarmSettings.get()
    assert feed_service.concentrate_increase_warning(
        barn_id=barn.id, new_ration=ration, new_start_date=date.today(), fs=fs,
    ) is None


def test_concentrate_increase_warning_fires_on_big_jump(app):
    barn = make_barn()
    fs = FarmSettings.get()
    old_ration = _make_ration("قديمة", 20)
    db.session.add(FeedBarnPlan(
        barn_id=barn.id, ration_id=old_ration.id, daily_qty_per_animal_kg=1,
        start_date=date.today() - timedelta(days=10),
    ))
    db.session.commit()

    new_ration = _make_ration("جديدة", 60)  # زيادة 40 نقطة خلال أقل من أسبوعين
    warning = feed_service.concentrate_increase_warning(
        barn_id=barn.id, new_ration=new_ration, new_start_date=date.today(), fs=fs,
    )
    assert warning is not None
    assert warning["increase"] > fs.concentrate_increase_max_percent_weekly


def test_concentrate_increase_warning_none_within_limit(app):
    barn = make_barn()
    fs = FarmSettings.get()
    old_ration = _make_ration("قديمة٢", 20)
    db.session.add(FeedBarnPlan(
        barn_id=barn.id, ration_id=old_ration.id, daily_qty_per_animal_kg=1,
        start_date=date.today() - timedelta(days=10),
    ))
    db.session.commit()

    new_ration = _make_ration("جديدة٢", 25)  # زيادة 5 نقاط فقط — ضمن الحد
    warning = feed_service.concentrate_increase_warning(
        barn_id=barn.id, new_ration=new_ration, new_start_date=date.today(), fs=fs,
    )
    assert warning is None


# ---------- نسبة الكالسيوم:الفسفور ----------

def test_ca_phosphorus_warning_none_within_tolerance(app):
    fs = FarmSettings.get()
    profile = {"calcium_percent": 1.0, "phosphorus_percent": 0.5}  # نسبة 2:1 بالضبط
    assert feed_service.ca_phosphorus_warning(profile, fs) is None


def test_ca_phosphorus_warning_fires_outside_tolerance(app):
    fs = FarmSettings.get()
    profile = {"calcium_percent": 3.0, "phosphorus_percent": 0.5}  # نسبة 6:1
    warning = feed_service.ca_phosphorus_warning(profile, fs)
    assert warning is not None
    assert warning["ratio"] == 6.0


# ---------- بروتوكول الإجهاض ----------

def test_record_abortion_isolates_and_creates_sampling_task(app):
    isolation_barn = make_barn(barn_no="ISO", barn_type="عزل")
    origin_barn = make_barn(barn_no="ORIG")
    animal = make_animal(animal_no="AB-01", gender="أنثى", barn_id=origin_barn.id)
    p = _confirmed_pregnancy(animal, date.today() - timedelta(days=30))

    result = record_abortion(pregnancy=p, outcome_date=date.today(), notes="اختبار", actor_user_id=1)

    assert result["isolated"] is True
    assert animal.barn_id == isolation_barn.id
    assert p.outcome == "abortion"
    assert result["sampling_task"].task_type == "abortion_sampling"


def test_record_abortion_creates_monitor_tasks_for_barnmates_only(app):
    make_barn(barn_no="ISO2", barn_type="عزل")
    origin_barn = make_barn(barn_no="ORIG2")
    animal = make_animal(animal_no="AB-02", gender="أنثى", barn_id=origin_barn.id)
    mate1 = make_animal(animal_no="AB-02-M1", barn_id=origin_barn.id)
    mate2 = make_animal(animal_no="AB-02-M2", barn_id=origin_barn.id)
    make_animal(animal_no="AB-02-OTHER")  # حظيرة ثانية — ما لازم يتضمن
    p = _confirmed_pregnancy(animal, date.today() - timedelta(days=30))

    result = record_abortion(pregnancy=p, outcome_date=date.today(), notes=None, actor_user_id=1)

    monitored_ids = {t.animal_id for t in result["monitor_tasks"]}
    assert monitored_ids == {mate1.id, mate2.id}
    assert all(t.task_type == "abortion_barn_monitor" for t in result["monitor_tasks"])


# ---------- بروتوكول الطوارئ (عمى مفاجئ) ----------

def test_emergency_symptom_isolates_and_returns_differential(app):
    """بند إضافي 127 المرحلة 4 — قائمة الطوارئ صارت جدولاً ديناميكياً
    (`EmergencySymptom`) بدل قاموس ثابت بالكود، فلازم نبذر الصف بأنفسنا
    هنا (نفس البيانات اللي `flask seed` يبذرها بالإنتاج)."""
    from app.models import Symptom, EmergencySymptom
    make_barn(barn_no="ISO3", barn_type="عزل")
    animal = make_animal(animal_no="EM-01")
    symptom = Symptom.query.filter_by(name="عمى مفاجئ / عتامة العين").first()
    if not symptom:
        symptom = Symptom(name="عمى مفاجئ / عتامة العين", is_primary=True)
        db.session.add(symptom)
        db.session.flush()
    db.session.add(EmergencySymptom(
        symptom_id=symptom.id, severity="شديدة",
        differential="اشتباه ليستريا / نقص فيتامين B1 (PEM)",
        advice="راجع الفحص البيطري الفوري.",
    ))
    db.session.commit()

    result = health_service.check_emergency_symptoms(
        animal_id=animal.id, symptom_names=["عمى مفاجئ / عتامة العين"], actor_user_id=1,
    )
    assert result is not None
    assert "ليستريا" in " ".join(result["differentials"])
    assert result["severities"] == ["شديدة"]


def test_emergency_symptom_none_for_normal_symptoms(app):
    animal = make_animal(animal_no="EM-02")
    result = health_service.check_emergency_symptoms(
        animal_id=animal.id, symptom_names=["حرارة", "إسهال"], actor_user_id=1,
    )
    assert result is None


# ---------- تأخر الشياع (تنبيه مستقل) ----------

def test_delayed_estrus_alert_independent_of_sale_score(app):
    animal = make_animal(animal_no="ES-01", gender="أنثى")
    fs = FarmSettings.get()
    from app.models import Mating
    db.session.add(Mating(female_id=animal.id, date=date.today() - timedelta(days=fs.female_delayed_conception_days + 10)))
    db.session.commit()

    alerts = alerts_service._delayed_estrus(fs)
    assert any(a["animal_id"] == animal.id for a in alerts)


# ---------- رعاية المولود الأولية ----------

def test_newborn_gets_cord_selenium_colostrum_tasks(app):
    mother = make_animal(animal_no="MOM-01", gender="أنثى")
    newborn = create_animal(
        animal_no="NB-01", source=AnimalSource.BIRTH, gender="أنثى",
        mother_id=mother.id, birth_date=date.today(),
    )
    task_types = {
        t.task_type for t in Task.query.filter_by(animal_id=newborn.id, source_type="IsolationPlan").all()
    }
    assert {"cord_antisepsis", "selenium_dose", "colostrum_check"} <= task_types
