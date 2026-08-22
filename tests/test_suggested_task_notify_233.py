"""بند إضافي 233 — زر "اعتماد وإرسال" كان يعتمد بس، ما يرسل أي إشعار
فعلياً للعامل المكلَّف، وشاشة "مهام مقترحة بانتظار الاعتماد" ما كانت
تظهر بالتنبيهات إطلاقاً."""
from datetime import date, datetime, timedelta, timezone

from app.extensions import db
from app.team import task_service as tsvc
from app.core import alerts_service
from app.models import Task
from tests.factories import make_barn, make_animal


def test_approve_suggested_task_notifies_assignee(app, owner, monkeypatch):
    barn = make_barn(responsible_worker_id=owner.id)
    task = tsvc.create_suggested_task(title="تنظيف المعالف", task_type="daily_care", barn_id=barn.id)
    assert task.status == "suggested"
    assert task.assignee_id == owner.id

    sent = []
    monkeypatch.setattr(
        "app.core.telegram_service.notify_user",
        lambda user, text: sent.append((user.id, text)),
    )

    tsvc.approve_suggested_task(task, actor=owner)
    assert task.status == "pending"
    assert len(sent) == 1
    assert sent[0][0] == owner.id
    assert "تنظيف المعالف" in sent[0][1]


def test_approve_suggested_task_without_assignee_sends_nothing(app, owner, monkeypatch):
    task = tsvc.create_suggested_task(title="فحص عام", task_type="daily_care", barn_id=None)
    assert task.assignee_id is None

    sent = []
    monkeypatch.setattr(
        "app.core.telegram_service.notify_user",
        lambda user, text: sent.append((user.id, text)),
    )
    tsvc.approve_suggested_task(task, actor=owner)
    assert sent == []


def test_stale_suggested_task_appears_as_alert(app):
    barn = make_barn()
    task = Task(title="رش وقائي متأخر", task_type="custom", status="suggested", barn_id=barn.id)
    db.session.add(task)
    db.session.commit()
    task.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=48)
    db.session.commit()

    alerts = alerts_service.get_alerts()
    matches = [a for a in alerts if a["category"] == "مهمة مقترحة بانتظار الاعتماد"]
    assert len(matches) == 1
    assert "رش وقائي متأخر" in matches[0]["label"]


def test_fresh_suggested_task_not_yet_flagged(app):
    barn = make_barn()
    task = tsvc.create_suggested_task(title="مهمة حديثة", task_type="custom", barn_id=barn.id)
    alerts = alerts_service.get_alerts()
    matches = [a for a in alerts if a["category"] == "مهمة مقترحة بانتظار الاعتماد"]
    assert matches == []


def test_alert_action_url_points_to_tasks_list(app):
    with app.test_request_context():
        alert = {"category": "مهمة مقترحة بانتظار الاعتماد", "animal_id": None}
        url = alerts_service.alert_action_url(alert)
        assert url is not None
        assert "/team/tasks" in url
