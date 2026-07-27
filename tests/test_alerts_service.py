"""اختبارات تنبيه "حظيرة بدون عامل مسؤول" (بند إضافي 56) — تذكير بس،
ما يمنع حفظ الحظيرة، ويختفي فور تعيين مسؤول."""
from app.extensions import db
from app.core.alerts_service import get_alerts
from app.models import Barn, User


def test_barn_without_worker_appears_in_alerts(app):
    barn = Barn(barn_no="AL-01", barn_name="حظيرة بدون مسؤول")
    db.session.add(barn)
    db.session.commit()

    alerts = get_alerts()
    matching = [a for a in alerts if a["category"] == "حظيرة بدون مسؤول" and a["barn_id"] == barn.id]
    assert len(matching) == 1
    assert matching[0]["urgent"] is False
    assert matching[0]["animal_id"] is None


def test_barn_with_worker_does_not_appear(app, worker):
    barn = Barn(barn_no="AL-02", barn_name="حظيرة فيها مسؤول", responsible_worker_id=worker.id)
    db.session.add(barn)
    db.session.commit()

    alerts = get_alerts()
    assert not any(
        a["category"] == "حظيرة بدون مسؤول" and a["barn_id"] == barn.id for a in alerts
    )


def test_alert_disappears_after_assigning_worker(app, worker):
    barn = Barn(barn_no="AL-03", barn_name="حظيرة تتحدث")
    db.session.add(barn)
    db.session.commit()

    assert any(
        a["category"] == "حظيرة بدون مسؤول" and a["barn_id"] == barn.id for a in get_alerts()
    )

    barn.responsible_worker_id = worker.id
    db.session.commit()

    assert not any(
        a["category"] == "حظيرة بدون مسؤول" and a["barn_id"] == barn.id for a in get_alerts()
    )
