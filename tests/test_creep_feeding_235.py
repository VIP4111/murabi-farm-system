"""بند إضافي 235 — تدرّج تغذية المولود التأسيسي (Creep Feeding):
0-19 يوم يُستثنى كلياً، 20-45 تدرّج خطي من 0 لهدف العلف البادئ،
46+ يُحسب حيوان نمو عادي."""
from datetime import date, timedelta

from app.extensions import db
from app.feed import feed_service as svc
from app.models import FarmSettings
from tests.factories import make_animal, make_barn


def _set_age(animal, days):
    animal.birth_date = date.today() - timedelta(days=days)
    db.session.commit()


def test_newborn_before_creep_start_fully_excluded(app):
    fs = FarmSettings.get()
    a = make_animal(animal_no="CR-01")
    _set_age(a, fs.creep_feed_start_age_days - 5)
    assert svc.infer_physiological_state(a) == "nursing_newborn"
    req = svc.daily_requirement(weight_kg=10, state="nursing_newborn", age_days=fs.creep_feed_start_age_days - 5)
    assert req["daily_dry_matter_kg"] == 0.0


def test_creep_feeding_ratio_zero_at_start(app):
    fs = FarmSettings.get()
    a = make_animal(animal_no="CR-02")
    _set_age(a, fs.creep_feed_start_age_days)
    assert svc.infer_physiological_state(a) == "creep_feeding"
    req = svc.daily_requirement(weight_kg=12, state="creep_feeding", age_days=fs.creep_feed_start_age_days)
    assert req["daily_dry_matter_kg"] == 0.0


def test_creep_feeding_ratio_full_at_weaning_boundary(app):
    fs = FarmSettings.get()
    age = fs.weaning_solid_feed_age_days - 1
    req = svc.daily_requirement(weight_kg=15, state="creep_feeding", age_days=age)
    ratio = svc.creep_feed_progress_ratio(age, fs)
    expected = round(fs.creep_feed_target_grams_per_day / 1000 * ratio, 3)
    assert req["daily_dry_matter_kg"] == expected
    assert 0 < req["daily_dry_matter_kg"] < fs.creep_feed_target_grams_per_day / 1000


def test_creep_feeding_ratio_linear_midpoint(app):
    fs = FarmSettings.get()
    mid_age = (fs.creep_feed_start_age_days + fs.weaning_solid_feed_age_days) // 2
    ratio = svc.creep_feed_progress_ratio(mid_age, fs)
    assert 0.35 < ratio < 0.65


def test_after_weaning_age_treated_as_normal_growth(app):
    fs = FarmSettings.get()
    a = make_animal(animal_no="CR-03")
    _set_age(a, fs.weaning_solid_feed_age_days + 5)
    state = svc.infer_physiological_state(a)
    assert state not in ("nursing_newborn", "creep_feeding")


def test_barn_report_shows_creep_feeding_bucket(app, logged_in_client):
    fs = FarmSettings.get()
    barn = make_barn()
    kid = make_animal(animal_no="CR-04", barn_id=barn.id)
    kid.weight = 12
    _set_age(kid, fs.creep_feed_start_age_days + 5)

    resp = logged_in_client.get(f"/feed/barn-report?barn_id={barn.id}")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "تغذية تأسيسية" in body
