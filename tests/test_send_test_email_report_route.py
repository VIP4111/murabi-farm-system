"""بند إضافي 160 (المرحلة ج) — زر "أرسل تقرير تجريبي الآن"، يسمح
لمن يدير البلاغات يتأكد إن إعداد SMTP يشتغل بدون انتظار الجدولة."""
from unittest.mock import patch

from app.extensions import db


def test_send_test_email_report_requires_reports_manage_permission(app, client):
    from app.models import Role, User
    role = Role.query.filter_by(name="worker").first()
    worker = User(name="عامل اختبار", phone="0599999180", role_id=role.id, language="ar")
    worker.set_password("test1234")
    db.session.add(worker)
    db.session.commit()

    client.post("/login", data={"phone": worker.phone, "password": "test1234"})
    resp = client.post("/settings/send-test-email-report")
    assert resp.status_code == 403


def test_send_test_email_report_by_owner_sends_and_flashes(app, client, owner):
    owner.email = "owner@example.com"
    db.session.commit()
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    with patch("app.core.email_service.send_email", return_value=True) as mock_send:
        resp = client.post("/settings/send-test-email-report", follow_redirects=True)
    assert resp.status_code == 200
    mock_send.assert_called_once()
    assert "تم إرسال التقرير" in resp.data.decode()
