"""اختبارات مؤشر ربط انخفاض استهلاك العلف بالإجهاد الحراري (بند إضافي
49) — توصية فقط، بدون أي تعديل تلقائي بالعليقة."""
from datetime import date, datetime, time, timedelta

from app.extensions import db
from app.feed.feed_service import heat_fcr_signal
from app.models import FeedMovement
from factories import make_animal, make_barn, make_feed, make_weather_reading


def _add_movement(feed, barn, day, quantity):
    db.session.add(FeedMovement(
        feed_id=feed.id, movement_type="out", quantity=quantity, barn_id=barn.id,
        created_at=datetime.combine(day, time(12, 0)),
    ))
    db.session.commit()


def _seed_baseline_and_recent(barn, feed, baseline_daily_kg, recent_daily_kg, as_of):
    recent_start = as_of - timedelta(days=2)  # نافذة أخيرة = 3 أيام
    for i in range(3):
        _add_movement(feed, barn, recent_start + timedelta(days=i), recent_daily_kg)

    baseline_end = recent_start - timedelta(days=1)
    baseline_start = baseline_end - timedelta(days=13)  # نافذة أساس = 14 يوم
    day = baseline_start
    while day <= baseline_end:
        _add_movement(feed, barn, day, baseline_daily_kg)
        day += timedelta(days=1)


def test_no_signal_without_hot_weather_reading(app):
    barn = make_barn()
    make_animal(barn_id=barn.id)
    feed = make_feed()
    _seed_baseline_and_recent(barn, feed, baseline_daily_kg=5, recent_daily_kg=1, as_of=date.today())

    assert heat_fcr_signal(barn_id=barn.id) is None


def test_no_signal_when_drop_below_threshold(app):
    barn = make_barn()
    make_animal(barn_id=barn.id)
    feed = make_feed()
    make_weather_reading(date.today(), thi=80.0, stress_level="moderate")
    # انخفاض بسيط (10%) — أقل من حد التنبيه (15%)
    _seed_baseline_and_recent(barn, feed, baseline_daily_kg=5.0, recent_daily_kg=4.5, as_of=date.today())

    assert heat_fcr_signal(barn_id=barn.id) is None


def test_signal_fires_on_hot_weather_and_big_consumption_drop(app):
    barn = make_barn()
    make_animal(barn_id=barn.id)
    feed = make_feed()
    make_weather_reading(date.today(), thi=91.3, stress_level="severe")
    _seed_baseline_and_recent(barn, feed, baseline_daily_kg=5.0, recent_daily_kg=1.0, as_of=date.today())

    signal = heat_fcr_signal(barn_id=barn.id)

    assert signal is not None
    assert signal["drop_pct"] > 15.0
    assert signal["peak_thi"] == 91.3
    assert "استهلاك العلف انخفض" in signal["recommendation"]
    assert "مالك" in signal["recommendation"]  # توصية فقط، مو تنفيذ تلقائي


def test_no_signal_without_animals(app):
    barn = make_barn()
    feed = make_feed()
    make_weather_reading(date.today(), thi=91.3, stress_level="severe")
    _seed_baseline_and_recent(barn, feed, baseline_daily_kg=5.0, recent_daily_kg=1.0, as_of=date.today())

    assert heat_fcr_signal(barn_id=barn.id) is None
