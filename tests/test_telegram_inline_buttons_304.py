"""بند إضافي 304 — طلبك: أزرار تفاعلية (Inline Keyboards) تحت ملخص
تيليجرام اليومي: عرض التنبيهات، مراجعة المهام، فتح المساعد الذكي."""
import os
from unittest.mock import patch, MagicMock

from app.extensions import db
from app.core import telegram_service
from app.core.daily_telegram_report_service import send_daily_report_now


def test_inline_keyboard_builds_one_button_per_row():
    markup = telegram_service.inline_keyboard([("زر واحد", "https://x.test/a"), ("زر ثاني", "https://x.test/b")])
    assert markup == {"inline_keyboard": [
        [{"text": "زر واحد", "url": "https://x.test/a"}],
        [{"text": "زر ثاني", "url": "https://x.test/b"}],
    ]}


def test_send_message_includes_reply_markup_when_given(app):
    os.environ["TELEGRAM_BOT_TOKEN"] = "fake-token"
    try:
        markup = telegram_service.inline_keyboard([("زر", "https://x.test/a")])
        with patch("app.core.telegram_service.requests.post") as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            telegram_service.send_message("999", "hello", reply_markup=markup)
        assert mock_post.call_args.kwargs["json"]["reply_markup"] == markup
    finally:
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)


def test_send_message_without_reply_markup_omits_key(app):
    os.environ["TELEGRAM_BOT_TOKEN"] = "fake-token"
    try:
        with patch("app.core.telegram_service.requests.post") as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            telegram_service.send_message("999", "hello")
        assert "reply_markup" not in mock_post.call_args.kwargs["json"]
    finally:
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)


def test_daily_telegram_report_includes_buttons_when_base_url_set(app, owner, monkeypatch):
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://murabi-farm-system.onrender.com")
    owner.telegram_chat_id = "42"
    db.session.commit()
    with patch("app.core.telegram_service.notify_user", return_value=True) as mock_notify:
        sent = send_daily_report_now()
    assert sent == 1
    kwargs = mock_notify.call_args.kwargs
    assert kwargs["reply_markup"] is not None
    labels = [btn[0]["text"] for btn in kwargs["reply_markup"]["inline_keyboard"]]
    assert any("التنبيهات" in label for label in labels)
    assert any("المهام" in label for label in labels)
    assert any("المساعد" in label for label in labels)


def test_daily_telegram_report_omits_buttons_without_base_url(app, owner, monkeypatch):
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    owner.telegram_chat_id = "43"
    db.session.commit()
    with patch("app.core.telegram_service.notify_user", return_value=True) as mock_notify:
        send_daily_report_now()
    assert mock_notify.call_args.kwargs["reply_markup"] is None
