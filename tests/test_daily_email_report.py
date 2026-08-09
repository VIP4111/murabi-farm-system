"""بند إضافي 160 (المرحلة ج) — تقرير يومي تلقائي بالبريد الإلكتروني.
نفس فلسفة test_telegram_service.py: mock للإرسال الفعلي، بدون شبكة
حقيقية بالاختبار."""
from unittest.mock import patch

from app.extensions import db
from app.core import email_service
from app.core.daily_email_report_service import (
    build_report_email, send_daily_report_now, generate_daily_email_report_if_needed,
)
from app.models import FarmSettings


def test_send_email_noop_without_resend_config(app, monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("EMAIL_FROM_ADDRESS", raising=False)
    assert email_service.send_email("a@b.com", "subj", "body") is False


def test_send_email_noop_without_recipient(app, monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "key123")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "from@example.com")
    assert email_service.send_email(None, "subj", "body") is False


def test_send_email_success_with_mocked_http(app, monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "key123")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "from@example.com")
    with patch("requests.post") as mock_post:
        mock_post.return_value.ok = True
        result = email_service.send_email("owner@example.com", "subj", "body")
    assert result is True
    mock_post.assert_called_once()
    assert mock_post.call_args.kwargs["headers"]["Authorization"] == "Bearer key123"
    assert mock_post.call_args.kwargs["json"]["to"] == ["owner@example.com"]


def test_send_email_handles_request_error(app, monkeypatch):
    import requests
    monkeypatch.setenv("RESEND_API_KEY", "key123")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "from@example.com")
    with patch("requests.post", side_effect=requests.RequestException("boom")):
        assert email_service.send_email("owner@example.com", "subj", "body") is False


def test_build_report_email_contains_key_sections(app):
    subject, body = build_report_email()
    assert "تقرير مراح بو علي" in subject
    assert "الرؤوس النشطة" in body
    assert "مهام مفتوحة" in body
    assert "بلاغات مفتوحة" in body


def test_send_daily_report_now_sends_only_to_users_with_email_and_permission(app, owner):
    owner.email = "owner@example.com"
    db.session.commit()
    with patch("app.core.email_service.send_email", return_value=True) as mock_send:
        sent = send_daily_report_now()
    assert sent == 1
    mock_send.assert_called_once()
    assert mock_send.call_args[0][0] == "owner@example.com"


def test_send_daily_report_now_skips_users_without_email(app, owner):
    with patch("app.core.email_service.send_email", return_value=True) as mock_send:
        sent = send_daily_report_now()
    assert sent == 0
    mock_send.assert_not_called()


def test_generate_daily_email_report_guards_against_duplicate_same_day(app, owner):
    owner.email = "owner@example.com"
    db.session.commit()
    with patch("app.core.email_service.send_email", return_value=True) as mock_send:
        generate_daily_email_report_if_needed()
        generate_daily_email_report_if_needed()
    mock_send.assert_called_once()
    settings = FarmSettings.get()
    from datetime import date
    assert settings.last_daily_email_report_sent == date.today()
