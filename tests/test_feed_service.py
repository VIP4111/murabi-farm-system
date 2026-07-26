"""اختبارات app/feed/feed_service.py — بند إضافي 46 (٣): حظيرة إلزامية
لحركة الصادر، وحظر السحب بالسالب (نفس قيد الصيدلية بالمخزون)."""
import pytest

from app.feed import feed_service
from factories import make_barn, make_feed


def test_out_movement_without_barn_is_rejected(app):
    feed = make_feed(available_qty=100)
    with pytest.raises(ValueError):
        feed_service.record_movement(feed=feed, movement_type="out", quantity=10, barn_id=None)
    assert feed.available_qty == 100


def test_out_movement_with_barn_succeeds(app):
    feed = make_feed(available_qty=100)
    barn = make_barn()
    mv = feed_service.record_movement(feed=feed, movement_type="out", quantity=10, barn_id=barn.id)
    assert feed.available_qty == 90
    assert mv.barn_id == barn.id


def test_in_movement_without_barn_is_allowed(app):
    feed = make_feed(available_qty=100)
    feed_service.record_movement(feed=feed, movement_type="in", quantity=50, barn_id=None)
    assert feed.available_qty == 150


def test_out_movement_exceeding_stock_is_rejected(app):
    feed = make_feed(available_qty=10)
    barn = make_barn()
    with pytest.raises(ValueError):
        feed_service.record_movement(feed=feed, movement_type="out", quantity=500, barn_id=barn.id)
    assert feed.available_qty == 10
