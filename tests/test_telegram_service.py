"""بند إضافي 157 — إشعارات فورية مجانية عبر تيليجرام بديلاً عن واتساب
المدفوع. الإرسال يتجاهل بصمت دائماً (بدون توكن، بدون chat_id، أو خطأ
شبكة) — إشعار فاشل ما يوقف أي عملية أساسية بالنظام."""
import os
from unittest.mock import patch, MagicMock

from app.core import telegram_service


def test_send_message_returns_false_without_token(app):
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    assert telegram_service.send_message("123", "hi") is False


def test_send_message_returns_false_without_chat_id(app):
    os.environ["TELEGRAM_BOT_TOKEN"] = "fake-token"
    try:
        assert telegram_service.send_message(None, "hi") is False
    finally:
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)


def test_send_message_calls_telegram_api_when_configured(app):
    os.environ["TELEGRAM_BOT_TOKEN"] = "fake-token"
    try:
        with patch("app.core.telegram_service.requests.post") as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            result = telegram_service.send_message("999", "hello")
        assert result is True
        mock_post.assert_called_once()
        assert "fake-token" in mock_post.call_args[0][0]
    finally:
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)


def test_send_message_handles_network_error_gracefully(app):
    os.environ["TELEGRAM_BOT_TOKEN"] = "fake-token"
    try:
        import requests
        with patch("app.core.telegram_service.requests.post", side_effect=requests.RequestException("boom")):
            result = telegram_service.send_message("999", "hello")
        assert result is False
    finally:
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)


def test_notify_user_with_no_chat_id_is_noop(app):
    class Dummy:
        telegram_chat_id = None
    assert telegram_service.notify_user(Dummy(), "hi") is False


def test_fetch_recent_chats_empty_without_token(app):
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    assert telegram_service.fetch_recent_chats() == []
