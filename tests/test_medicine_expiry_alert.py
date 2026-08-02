"""بند إضافي 94 — تنبيه قرب انتهاء صلاحية دواء. قبل هذا البند
Pharmacy.expiry_date كان مخزّناً بدون أي منطق تنبيه يستخدمه."""
from datetime import date, timedelta

from app.extensions import db
from app.core.alerts_service import get_alerts
from app.models import Pharmacy


def test_medicine_expiring_within_window_appears_not_urgent(app):
    p = Pharmacy(name="مضاد حيوي أ", expiry_date=date.today() + timedelta(days=3), available_qty=10, unit="مل")
    db.session.add(p)
    db.session.commit()

    alerts = get_alerts()
    matching = [a for a in alerts if a["category"] == "قرب انتهاء صلاحية دواء" and "مضاد حيوي أ" in a["label"]]
    assert len(matching) == 1
    assert matching[0]["urgent"] is False


def test_medicine_already_expired_is_urgent(app):
    p = Pharmacy(name="لقاح ب", expiry_date=date.today() - timedelta(days=2), available_qty=5, unit="جرعة")
    db.session.add(p)
    db.session.commit()

    alerts = get_alerts()
    matching = [a for a in alerts if a["category"] == "قرب انتهاء صلاحية دواء" and "لقاح ب" in a["label"]]
    assert len(matching) == 1
    assert matching[0]["urgent"] is True


def test_medicine_far_from_expiry_does_not_appear(app):
    p = Pharmacy(name="مكمّل ج", expiry_date=date.today() + timedelta(days=365), available_qty=1, unit="علبة")
    db.session.add(p)
    db.session.commit()

    alerts = get_alerts()
    matching = [a for a in alerts if "مكمّل ج" in a["label"]]
    assert len(matching) == 0


def test_medicine_without_expiry_date_never_appears(app):
    p = Pharmacy(name="دواء بدون تاريخ", expiry_date=None, available_qty=1, unit="علبة")
    db.session.add(p)
    db.session.commit()

    alerts = get_alerts()
    matching = [a for a in alerts if "دواء بدون تاريخ" in a["label"]]
    assert len(matching) == 0


def test_inactive_medicine_expiry_not_shown(app):
    p = Pharmacy(name="دواء موقوف", expiry_date=date.today() + timedelta(days=1), available_qty=1, unit="علبة", status="inactive")
    db.session.add(p)
    db.session.commit()

    alerts = get_alerts()
    matching = [a for a in alerts if "دواء موقوف" in a["label"]]
    assert len(matching) == 0
