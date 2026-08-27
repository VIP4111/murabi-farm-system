"""بند إضافي 278 — طلبين صريحين بنفس التبادل:
(1) صفحة تفصيل المهمة ما كانت تعرض العامل المكلَّف إطلاقاً.
(2) "مهام يصعب تأجيلها": مثال العلف — لو الموعد 8، والمهلة ساعة، فالساعة
9 يعتبر إنذار يوصل لصاحب الحلال، حتى لو العامل أكد إنه أنجزها."""
from datetime import date, datetime, time, timedelta

from app.extensions import db
from app.core import alerts_service, feeding_schedule_service as feed_svc
from app.models import BarnFeedingSchedule, FarmSettings, Task
from app.team import task_service
from factories import make_barn


def _add_schedule(barn, meal_time):
    s = BarnFeedingSchedule(barn_id=barn.id, meal_time=meal_time, sort_order=0)
    db.session.add(s)
    db.session.commit()
    return s


def test_feeding_task_gets_due_time_from_schedule(app):
    barn = make_barn(barn_no="TC-01")
    _add_schedule(barn, time(8, 0))
    created = feed_svc.generate_feeding_tasks(now=datetime.combine(date.today(), time(8, 5)))
    assert created[0].due_time == time(8, 0)


def test_not_yet_late_within_grace_window(app, owner):
    fs = FarmSettings.get()
    fs.task_late_grace_minutes = 60
    db.session.commit()
    task = task_service.create_suggested_task(
        title="🥣 وجبة علف اختبار", task_type="feeding_schedule", barn_id=make_barn(barn_no="TC-02").id,
        due_date=date.today(), due_time=time(8, 0), auto_approve=True,
    )
    alerts = alerts_service.get_alerts(now=datetime.combine(date.today(), time(8, 30)))
    assert not any(a.get("task_id") == task.id for a in alerts)


def test_late_pending_task_triggers_urgent_alert(app, owner):
    fs = FarmSettings.get()
    fs.task_late_grace_minutes = 60
    db.session.commit()
    barn = make_barn(barn_no="TC-03")
    noon = datetime.combine(date.today(), time(12, 0))
    task = task_service.create_suggested_task(
        title="🥣 وجبة علف اختبار متأخرة", task_type="feeding_schedule", barn_id=barn.id,
        due_date=date.today(), due_time=time(9, 0), auto_approve=True,
    )
    alerts = alerts_service.get_alerts(now=noon)
    matching = [a for a in alerts if a.get("task_id") == task.id]
    assert len(matching) == 1
    assert matching[0]["category"] == "مهمة متأخرة عن موعدها"
    assert matching[0]["urgent"] is True


def test_completed_late_still_alerts_owner(app, owner):
    """طلبك الصريح: حتى لو العامل أنجزها، لو بعد الموعد+المهلة يعتبر
    إنذار يوصل لصاحب الحلال."""
    fs = FarmSettings.get()
    fs.task_late_grace_minutes = 60
    db.session.commit()
    barn = make_barn(barn_no="TC-04")
    task = task_service.create_suggested_task(
        title="🥣 وجبة علف اختبار أُنجزت متأخرة", task_type="feeding_schedule", barn_id=barn.id,
        due_date=date.today(), due_time=time(8, 0), auto_approve=True,
    )
    task.assignee_id = owner.id
    task.status = "done"
    task.completed_at = datetime.combine(date.today(), time(11, 0))  # بعد الموعد+المهلة بكثير
    db.session.commit()

    alerts = alerts_service.get_alerts(now=datetime.combine(date.today(), time(12, 0)))
    matching = [a for a in alerts if a.get("task_id") == task.id]
    assert len(matching) == 1
    assert matching[0]["category"] == "مهمة أُنجزت متأخرة عن موعدها"


def test_completed_on_time_does_not_alert(app, owner):
    fs = FarmSettings.get()
    fs.task_late_grace_minutes = 60
    db.session.commit()
    barn = make_barn(barn_no="TC-05")
    task = task_service.create_suggested_task(
        title="🥣 وجبة علف اختبار بالوقت", task_type="feeding_schedule", barn_id=barn.id,
        due_date=date.today(), due_time=time(8, 0), auto_approve=True,
    )
    task.status = "done"
    task.completed_at = datetime.combine(date.today(), time(8, 20))
    db.session.commit()

    alerts = alerts_service.get_alerts(now=datetime.combine(date.today(), time(8, 30)))
    assert not any(a.get("task_id") == task.id for a in alerts)


def test_task_without_due_time_never_triggers_this_alert(app, owner):
    barn = make_barn(barn_no="TC-06")
    task = task_service.create_suggested_task(
        title="مهمة عادية بدون موعد وقت", task_type="custom", barn_id=barn.id,
        due_date=date.today() - timedelta(days=5), auto_approve=True,
    )
    alerts = alerts_service.get_alerts()
    assert not any(a.get("task_id") == task.id for a in alerts)


def test_task_detail_shows_assignee(app, logged_in_client, owner):
    barn = make_barn(barn_no="TC-07")
    task = task_service.create_suggested_task(
        title="مهمة اختبار عرض العامل", task_type="custom", barn_id=barn.id,
        due_date=date.today(), auto_approve=True,
    )
    task.assignee_id = owner.id
    db.session.commit()
    resp = logged_in_client.get(f"/team/tasks/{task.id}")
    body = resp.data.decode()
    assert owner.name in body
