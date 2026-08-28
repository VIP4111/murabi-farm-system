"""بند إضافي 296 — المرحلة ١ من خطة "عقل المزرعة" الاستباقية: توقّع
نفاد علف قريب بتحليل إحصائي بسيط لمعدل استهلاك حركات `FeedMovement`
الفعلية مقابل `Feed.available_qty`، بدون أي نموذج ذكاء اصطناعي."""
from datetime import datetime, timedelta

from app.extensions import db
from app.core import alerts_service
from app.models import FeedMovement
from factories import make_feed


def _add_out(feed, quantity, days_ago):
    db.session.add(FeedMovement(
        feed_id=feed.id, movement_type="out", quantity=quantity,
        created_at=datetime.now() - timedelta(days=days_ago),
    ))
    db.session.commit()


def test_feed_running_low_soon_triggers_alert(app):
    feed = make_feed(name="ذرة صفراء", available_qty=10)
    # معدل استهلاك 5 وحدات/يوم آخر 3 أيام — المتبقي 10 ينفد خلال يومين تقريباً
    _add_out(feed, 5, 3)
    _add_out(feed, 5, 2)
    _add_out(feed, 5, 1)

    alerts = alerts_service._feed_depletion_forecast()
    assert len(alerts) == 1
    assert "ذرة صفراء" in alerts[0]["label"]
    assert alerts[0]["urgent"] is True  # يومين أو أقل


def test_feed_with_healthy_stock_not_flagged(app):
    feed = make_feed(name="برسيم", available_qty=1000)
    _add_out(feed, 2, 3)
    _add_out(feed, 2, 2)
    _add_out(feed, 2, 1)

    alerts = alerts_service._feed_depletion_forecast()
    assert alerts == []


def test_feed_with_too_few_movements_ignored(app):
    feed = make_feed(name="أملاح", available_qty=1)
    _add_out(feed, 5, 1)
    _add_out(feed, 5, 0)  # حركتين بس — أقل من الحد الأدنى الموثوق

    alerts = alerts_service._feed_depletion_forecast()
    assert alerts == []


def test_feed_already_out_of_stock_is_urgent(app):
    feed = make_feed(name="مركّز نمو", available_qty=0)
    _add_out(feed, 3, 3)
    _add_out(feed, 3, 2)
    _add_out(feed, 3, 1)

    alerts = alerts_service._feed_depletion_forecast()
    assert len(alerts) == 1
    assert alerts[0]["urgent"] is True


def test_feed_depletion_alert_included_in_get_alerts(app):
    feed = make_feed(name="فيتامينات", available_qty=2)
    _add_out(feed, 5, 3)
    _add_out(feed, 5, 2)
    _add_out(feed, 5, 1)

    alerts = alerts_service.get_alerts()
    assert any(a["category"] == "توقّع نفاد علف" for a in alerts)
