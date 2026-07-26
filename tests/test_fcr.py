"""اختبارات معدل التحويل الغذائي FCR (بند إضافي 48، القسم الثاني-١)."""
from datetime import date, timedelta

from app.extensions import db
from app.feed.feed_service import calculate_fcr
from app.models import FeedMovement
from app.models.animal_log import AnimalWeight
from factories import make_animal, make_barn, make_feed


def _add_weight(animal, when, weight):
    db.session.add(AnimalWeight(animal_id=animal.id, date=when, weight=weight))
    db.session.commit()


def test_fcr_computed_from_feed_consumed_and_weight_gain(app):
    barn = make_barn()
    animal = make_animal(barn_id=barn.id)
    feed = make_feed(unit_price=2.0)

    start = date.today() - timedelta(days=10)
    end = date.today()
    _add_weight(animal, start, 20)
    _add_weight(animal, end, 25)  # +5 kg gain

    mv = FeedMovement(feed_id=feed.id, movement_type="out", quantity=25, barn_id=barn.id)
    db.session.add(mv)
    db.session.commit()

    result = calculate_fcr(barn_id=barn.id, start_date=start, end_date=end)
    assert result["total_feed_kg"] == 25
    assert result["total_weight_gain_kg"] == 5
    assert result["fcr"] == 5.0  # 25kg feed / 5kg gain
    assert result["total_feed_cost"] == 50.0  # 25 * 2.0
    assert result["cost_per_kg_gained"] == 10.0
    assert result["animals_with_data"] == 1


def test_fcr_none_when_no_weight_data(app):
    barn = make_barn()
    make_animal(barn_id=barn.id)
    result = calculate_fcr(barn_id=barn.id, start_date=date.today() - timedelta(days=5), end_date=date.today())
    assert result["fcr"] is None
    assert result["animals_with_data"] == 0


def test_fcr_excludes_movements_outside_barn(app):
    barn1 = make_barn(barn_no="B1")
    barn2 = make_barn(barn_no="B2")
    animal = make_animal(barn_id=barn1.id)
    feed = make_feed(unit_price=1.0)

    start = date.today() - timedelta(days=5)
    end = date.today()
    _add_weight(animal, start, 10)
    _add_weight(animal, end, 12)

    db.session.add(FeedMovement(feed_id=feed.id, movement_type="out", quantity=100, barn_id=barn2.id))
    db.session.commit()

    result = calculate_fcr(barn_id=barn1.id, start_date=start, end_date=end)
    assert result["total_feed_kg"] == 0
