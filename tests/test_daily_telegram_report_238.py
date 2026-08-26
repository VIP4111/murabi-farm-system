"""بند إضافي 238 — بند 4 (والأخير) من خطة الـ4 نقاط الواقعية: ملخص
يومي موحّد بتيليجرام. نفس بنية test_daily_email_report.py بالضبط،
بس بقناة تيليجرام بدل البريد."""
from unittest.mock import patch

from app.extensions import db
from app.core.daily_telegram_report_service import (
    send_daily_report_now, generate_daily_telegram_report_if_needed,
)
from app.models import FarmSettings


def test_send_daily_report_now_sends_only_to_users_with_chat_id_and_permission(app, owner):
    owner.telegram_chat_id = "111222333"
    db.session.commit()
    with patch("app.core.telegram_service.notify_user", return_value=True) as mock_send:
        sent = send_daily_report_now()
    assert sent == 1
    mock_send.assert_called_once()
    assert mock_send.call_args[0][0].id == owner.id
    assert "تقرير مراح بو علي" in mock_send.call_args[0][1]


def test_send_daily_report_now_skips_users_without_chat_id(app, owner):
    with patch("app.core.telegram_service.notify_user", return_value=True) as mock_send:
        sent = send_daily_report_now()
    assert sent == 0
    mock_send.assert_not_called()


def test_generate_daily_telegram_report_guards_against_duplicate_same_day(app, owner):
    owner.telegram_chat_id = "111222333"
    db.session.commit()
    with patch("app.core.telegram_service.notify_user", return_value=True) as mock_send:
        generate_daily_telegram_report_if_needed()
        generate_daily_telegram_report_if_needed()
    mock_send.assert_called_once()
    settings = FarmSettings.get()
    from datetime import date
    assert settings.last_daily_telegram_report_sent == date.today()


def test_email_and_telegram_guards_are_independent(app, owner):
    """فشل/تعطيل قناة وحدة ما يوقف الثانية — حارسين منفصلين تماماً."""
    owner.telegram_chat_id = "111222333"
    owner.email = "owner@example.com"
    db.session.commit()
    with patch("app.core.telegram_service.notify_user", return_value=False):
        generate_daily_telegram_report_if_needed()
    settings = FarmSettings.get()
    assert settings.last_daily_telegram_report_sent is not None
    assert settings.last_daily_email_report_sent is None


def test_send_test_telegram_report_route(app, logged_in_client, owner):
    owner.telegram_chat_id = "111222333"
    db.session.commit()
    with patch("app.core.telegram_service.notify_user", return_value=True):
        resp = logged_in_client.post("/settings/send-test-telegram-report", follow_redirects=True)
    assert resp.status_code == 200
    assert "تم إرسال الملخص فعلياً" in resp.data.decode()
