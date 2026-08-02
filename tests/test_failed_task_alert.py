"""بند إضافي 99 — تنبيه للمهام المتعذّرة بانتظار المراجعة. قبل هذا
البند، fail_task كان يسجّل الحالة والسبب بس بدون أي أثر يذكّر أحد."""
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import Task
from app.core.alerts_service import get_alerts


def _failed_task(days_ago=1, reason="نقص الأدوات", title="مهمة متعذّرة اختبار"):
    t = Task(
        title=title, task_type="custom", status="failed",
        failed_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_ago),
        failure_reason=reason,
    )
    db.session.add(t)
    db.session.commit()
    return t


def test_recent_failed_task_appears_in_alerts(app):
    _failed_task(days_ago=1)

    alerts = get_alerts()
    matching = [a for a in alerts if a["category"] == "مهمة متعذّرة بانتظار المراجعة"]
    assert len(matching) == 1
    assert matching[0]["urgent"] is True
    assert "نقص الأدوات" in matching[0]["label"]


def test_old_failed_task_does_not_appear(app):
    _failed_task(days_ago=10)

    alerts = get_alerts()
    matching = [a for a in alerts if a["category"] == "مهمة متعذّرة بانتظار المراجعة"]
    assert len(matching) == 0


def test_pending_task_does_not_appear_as_failed(app):
    t = Task(title="مهمة عادية", task_type="custom", status="pending")
    db.session.add(t)
    db.session.commit()

    alerts = get_alerts()
    matching = [a for a in alerts if a["category"] == "مهمة متعذّرة بانتظار المراجعة"]
    assert len(matching) == 0
