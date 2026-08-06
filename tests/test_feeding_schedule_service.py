"""اختبارات مهام وجبات العلف حسب جدول كل حظيرة (بند إضافي 131) — مهمة
تُنشأ فقط بعد وصول موعد الوجبة (مقارنة وقت، مو تاريخ بس مثل
`daily_task_service`)، ولا تكرار عند استدعاء متكرر لنفس الحظيرة/الموعد/اليوم."""
from datetime import date, datetime, time, timedelta

from app.extensions import db
from app.core import feeding_schedule_service as svc
from app.models import BarnFeedingSchedule
from factories import make_barn

BEFORE_BREAKFAST = datetime.combine(date.today(), time(6, 0))
AFTER_BREAKFAST = datetime.combine(date.today(), time(7, 30))
AFTER_LUNCH = datetime.combine(date.today(), time(13, 0))


def _add_schedule(barn, meal_time, sort_order=0):
    s = BarnFeedingSchedule(barn_id=barn.id, meal_time=meal_time, sort_order=sort_order)
    db.session.add(s)
    db.session.commit()
    return s


def test_no_task_before_meal_time(app):
    barn = make_barn(barn_no="F-01")
    _add_schedule(barn, time(7, 0))
    created = svc.generate_feeding_tasks(now=BEFORE_BREAKFAST)
    assert created == []


def test_task_created_once_meal_time_passed(app):
    barn = make_barn(barn_no="F-02")
    _add_schedule(barn, time(7, 0))
    created = svc.generate_feeding_tasks(now=AFTER_BREAKFAST)
    assert len(created) == 1
    assert barn.barn_name in created[0].title
    assert created[0].barn_id == barn.id
    assert created[0].status == "pending"
    assert created[0].source_type == svc.SOURCE_TYPE


def test_second_call_same_day_creates_nothing_new(app):
    barn = make_barn(barn_no="F-03")
    _add_schedule(barn, time(7, 0))
    first = svc.generate_feeding_tasks(now=AFTER_BREAKFAST)
    second = svc.generate_feeding_tasks(now=AFTER_BREAKFAST)
    assert len(first) == 1
    assert second == []


def test_multiple_meal_times_generate_independently(app):
    barn = make_barn(barn_no="F-04")
    _add_schedule(barn, time(7, 0), sort_order=0)
    _add_schedule(barn, time(12, 0), sort_order=1)

    created_morning = svc.generate_feeding_tasks(now=AFTER_BREAKFAST)
    assert len(created_morning) == 1

    created_noon = svc.generate_feeding_tasks(now=AFTER_LUNCH)
    assert len(created_noon) == 1
    assert created_morning[0].id != created_noon[0].id


def test_barn_without_schedule_generates_nothing(app):
    make_barn(barn_no="F-05")
    created = svc.generate_feeding_tasks(now=AFTER_LUNCH)
    assert created == []


def test_different_days_generate_separate_tasks(app):
    barn = make_barn(barn_no="F-06")
    _add_schedule(barn, time(7, 0))
    today_task = svc.generate_feeding_tasks(now=AFTER_BREAKFAST)
    assert len(today_task) == 1

    tomorrow = AFTER_BREAKFAST + timedelta(days=1)
    tomorrow_task = svc.generate_feeding_tasks(now=tomorrow)
    assert len(tomorrow_task) == 1
    assert tomorrow_task[0].id != today_task[0].id
