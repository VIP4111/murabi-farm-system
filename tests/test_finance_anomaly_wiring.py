"""بند إضافي 161 — تأكيد إن حفظ عملية مالية شاذة عبر /finance/new
يحاول يرسل إشعار تيليجرام فعلياً (مع mock)."""
from datetime import date
from unittest.mock import patch

from app.extensions import db
from app.models import Finance


def _seed_history(category="علف", amount=100.0, n=4):
    for _ in range(n):
        db.session.add(Finance(date=date.today(), operation_type="purchase", category=category, amount=amount))
    db.session.commit()


def test_anomalous_finance_entry_notifies_via_telegram(app, client, owner):
    owner.telegram_chat_id = "321"
    db.session.commit()
    _seed_history()

    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    with patch("app.core.telegram_service.notify_user") as mock_notify:
        resp = client.post("/finance/new", data={
            "date": date.today().isoformat(), "operation_type": "purchase",
            "category": "علف", "amount": "900",
        }, follow_redirects=True)
    assert resp.status_code == 200
    mock_notify.assert_called_once()
    assert "غير معتادة" in mock_notify.call_args[0][1]


def test_normal_finance_entry_does_not_notify(app, client, owner):
    owner.telegram_chat_id = "322"
    db.session.commit()
    _seed_history()

    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    with patch("app.core.telegram_service.notify_user") as mock_notify:
        client.post("/finance/new", data={
            "date": date.today().isoformat(), "operation_type": "purchase",
            "category": "علف", "amount": "105",
        }, follow_redirects=True)
    mock_notify.assert_not_called()
