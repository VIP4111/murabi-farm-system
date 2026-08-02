"""بند إضافي 97 — كشف مبكر لتباطؤ نمو مشبوه من سجلات الوزن الموجودة
أصلاً. قبل هذا البند ما فيه أي مقارنة بين رؤوس نفس الحظيرة."""
from datetime import date, timedelta

from app.extensions import db
from app.models import AnimalWeight
from app.core.alerts_service import get_alerts
from factories import make_animal, make_barn


def _add_weights(animal, start_weight, daily_gain, days_ago_start=60, days_ago_end=0):
    start = date.today() - timedelta(days=days_ago_start)
    end = date.today() - timedelta(days=days_ago_end)
    total_days = (start - end).days * -1
    db.session.add(AnimalWeight(animal_id=animal.id, date=start, weight=start_weight))
    db.session.add(AnimalWeight(animal_id=animal.id, date=end, weight=start_weight + daily_gain * total_days))
    db.session.commit()


def test_underperforming_animal_flagged_against_barn_average(app):
    barn = make_barn()
    normal1 = make_animal(animal_no="N-01", barn_id=barn.id)
    normal2 = make_animal(animal_no="N-02", barn_id=barn.id)
    slow = make_animal(animal_no="SLOW-01", barn_id=barn.id)
    _add_weights(normal1, 20, daily_gain=0.2)
    _add_weights(normal2, 20, daily_gain=0.2)
    _add_weights(slow, 20, daily_gain=0.02)  # أبطأ بكثير من المتوسط

    alerts = get_alerts()
    matching = [a for a in alerts if a["category"] == "تباطؤ نمو مشبوه" and "SLOW-01" in a["label"]]
    assert len(matching) == 1
    assert matching[0]["urgent"] is False
    others = [a for a in alerts if a["category"] == "تباطؤ نمو مشبوه" and a["animal_id"] in (normal1.id, normal2.id)]
    assert len(others) == 0


def test_weight_loss_is_always_urgent(app):
    barn = make_barn()
    normal1 = make_animal(animal_no="N-11", barn_id=barn.id)
    normal2 = make_animal(animal_no="N-12", barn_id=barn.id)
    losing = make_animal(animal_no="LOSS-01", barn_id=barn.id)
    _add_weights(normal1, 20, daily_gain=0.2)
    _add_weights(normal2, 20, daily_gain=0.2)
    _add_weights(losing, 20, daily_gain=-0.1)

    alerts = get_alerts()
    matching = [a for a in alerts if "LOSS-01" in a["label"]]
    assert len(matching) == 1
    assert matching[0]["urgent"] is True


def test_small_cohort_below_minimum_is_skipped(app):
    barn = make_barn()
    a1 = make_animal(animal_no="SM-01", barn_id=barn.id)
    a2 = make_animal(animal_no="SM-02", barn_id=barn.id)
    _add_weights(a1, 20, daily_gain=0.2)
    _add_weights(a2, 20, daily_gain=0.01)  # كان بيُعتبر متباطئ، لكن الحظيرة فيها رأسين بس

    alerts = get_alerts()
    matching = [a for a in alerts if a["category"] == "تباطؤ نمو مشبوه"]
    assert len(matching) == 0


def test_animal_with_single_weight_record_ignored(app):
    barn = make_barn()
    a1 = make_animal(animal_no="ONE-01", barn_id=barn.id)
    a2 = make_animal(animal_no="ONE-02", barn_id=barn.id)
    a3 = make_animal(animal_no="ONE-03", barn_id=barn.id)
    _add_weights(a1, 20, daily_gain=0.2)
    _add_weights(a2, 20, daily_gain=0.2)
    db.session.add(AnimalWeight(animal_id=a3.id, date=date.today(), weight=20))
    db.session.commit()

    alerts = get_alerts()
    matching = [a for a in alerts if "ONE-03" in a["label"]]
    assert len(matching) == 0
