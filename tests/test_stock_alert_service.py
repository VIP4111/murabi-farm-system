"""بند إضافي 162 (المرحلة د-1) — إشعار تيليجرام فوري لنقص مخزون
حرج، فور سحب المخزون تحت الحد الأدنى المضبوط."""
from unittest.mock import patch

from app.extensions import db
from app.core import stock_alert_service as svc
from factories import make_pharmacy, make_feed


def test_no_notification_without_min_stock_configured(app, owner):
    owner.telegram_chat_id = "1"
    db.session.commit()
    pharmacy = make_pharmacy(available_qty=0)  # min_stock_qty افتراضياً 0
    with patch("app.core.telegram_service.notify_user") as mock_notify:
        svc.check_pharmacy_stock(pharmacy)
    mock_notify.assert_not_called()


def test_no_notification_when_above_min_stock(app, owner):
    owner.telegram_chat_id = "2"
    db.session.commit()
    pharmacy = make_pharmacy(available_qty=50)
    pharmacy.min_stock_qty = 10
    db.session.commit()
    with patch("app.core.telegram_service.notify_user") as mock_notify:
        svc.check_pharmacy_stock(pharmacy)
    mock_notify.assert_not_called()


def test_notifies_when_pharmacy_stock_at_or_below_min(app, owner):
    owner.telegram_chat_id = "3"
    db.session.commit()
    pharmacy = make_pharmacy(available_qty=5)
    pharmacy.min_stock_qty = 10
    db.session.commit()
    with patch("app.core.telegram_service.notify_user") as mock_notify:
        svc.check_pharmacy_stock(pharmacy)
    mock_notify.assert_called_once()
    assert pharmacy.name in mock_notify.call_args[0][1]


def test_notifies_when_feed_stock_at_or_below_min(app, owner):
    owner.telegram_chat_id = "4"
    db.session.commit()
    feed = make_feed(available_qty=5)
    feed.min_stock_qty = 20
    db.session.commit()
    with patch("app.core.telegram_service.notify_user") as mock_notify:
        svc.check_feed_stock(feed)
    mock_notify.assert_called_once()
