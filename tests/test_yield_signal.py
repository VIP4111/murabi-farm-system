"""اختبارات المؤشر الداخلي لتوقيت البيع (بند إضافي 48، القسم الثاني-٣)
— مؤشر تكلفة/نمو داخلي بس، بدون أي بيانات سوق خارجية (قرار المستخدم
الصريح)."""
from datetime import date, timedelta

from app.extensions import db
from app.core.smart_sale_service import marginal_feeding_signal
from app.models import FeedBarnPlan, FeedRation, FeedRationItem
from app.models.animal_log import AnimalWeight
from factories import make_animal, make_barn, make_feed


def _setup_barn_with_ration(daily_cost_per_kg=2.0):
    barn = make_barn()
    feed = make_feed(unit_price=daily_cost_per_kg)
    ration = FeedRation(name="وصفة اختبار")
    db.session.add(ration)
    db.session.flush()
    db.session.add(FeedRationItem(ration_id=ration.id, feed_id=feed.id, percent=100))
    db.session.add(FeedBarnPlan(
        barn_id=barn.id, ration_id=ration.id, daily_qty_per_animal_kg=1.0,
        start_date=date.today() - timedelta(days=30),
    ))
    db.session.commit()
    return barn


def test_no_signal_without_two_weight_records(app):
    barn = _setup_barn_with_ration()
    animal = make_animal(barn_id=barn.id, price=200)
    assert marginal_feeding_signal(animal) is None


def test_no_signal_when_marginal_cost_within_normal_range(app):
    barn = _setup_barn_with_ration(daily_cost_per_kg=0.01)  # علف رخيص جداً
    animal = make_animal(barn_id=barn.id, price=500)
    animal.weight = 30
    db.session.commit()
    db.session.add(AnimalWeight(animal_id=animal.id, date=date.today() - timedelta(days=10), weight=25))
    db.session.add(AnimalWeight(animal_id=animal.id, date=date.today(), weight=30))
    db.session.commit()
    assert marginal_feeding_signal(animal) is None


def test_signal_fires_when_marginal_cost_exceeds_historical_average(app):
    # علف غالي جداً + زيادة وزن ضئيلة -> تكلفة حدية عالية جداً للكيلو،
    # مقابل سعر شراء رخيص (متوسط تاريخي منخفض) -> لازم تطلع إشارة.
    barn = _setup_barn_with_ration(daily_cost_per_kg=1000.0)
    animal = make_animal(barn_id=barn.id, price=50)
    animal.weight = 30
    db.session.commit()
    db.session.add(AnimalWeight(animal_id=animal.id, date=date.today() - timedelta(days=10), weight=29.9))
    db.session.add(AnimalWeight(animal_id=animal.id, date=date.today(), weight=30))
    db.session.commit()

    signal = marginal_feeding_signal(animal)
    assert signal is not None
    assert signal["marginal_cost_per_kg"] > signal["historical_cost_per_kg"]
    assert "التكلفة الحدية" in signal["reason"]


def test_no_signal_when_weight_did_not_increase(app):
    barn = _setup_barn_with_ration()
    animal = make_animal(barn_id=barn.id, price=200)
    animal.weight = 30
    db.session.commit()
    db.session.add(AnimalWeight(animal_id=animal.id, date=date.today() - timedelta(days=10), weight=30))
    db.session.add(AnimalWeight(animal_id=animal.id, date=date.today(), weight=30))
    db.session.commit()
    assert marginal_feeding_signal(animal) is None
