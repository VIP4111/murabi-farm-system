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
    """بند إضافي 303 — صار يرجّع (عنوان، نص، HTML) بدل (عنوان، نص) —
    تصحيح خلط الأرقام: بدل رقم واحد "مهام مفتوحة/متأخرة" يخلط 3 حالات،
    صارت 3 أرقام منفصلة صراحة."""
    subject, text_body, html_body = build_report_email()
    assert "تقرير مراح بو علي" in subject
    assert "القطيع النشط" in text_body
    assert "متأخرة فعلاً" in text_body
    assert "بلاغات مفتوحة" in text_body
    assert "<html" not in html_body.lower()  # قطعة HTML جزئية تُدرَج بجسم الرسالة، مو مستند كامل
    assert "روابط سريعة" in html_body or "قل" in html_body  # تأكيد وجود قسم الروابط


def test_build_report_email_task_breakdown_is_not_conflated(app, owner):
    """أهم اختبار لتصحيح بند 303: مهمة بدون تاريخ استحقاق لا تُحسب
    ضمن 'متأخرة فعلاً' — الخلط القديم كان يجمعهم برقم واحد مضلِّل."""
    from app.team import task_service
    from datetime import date, timedelta

    task_service.assign_task(actor=owner, title="مهمة بدون تاريخ")
    task_service.assign_task(actor=owner, title="مهمة متأخرة فعلاً", due_date=date.today() - timedelta(days=2))

    subject, text_body, html_body = build_report_email()
    assert "متأخرة فعلاً: 1" in text_body
    assert "بدون تاريخ: 1" in text_body


def test_build_report_email_includes_action_links_when_base_url_set(app, monkeypatch):
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://murabi-farm-system.onrender.com")
    subject, text_body, html_body = build_report_email()
    assert "https://murabi-farm-system.onrender.com/alerts" in text_body
    assert "https://murabi-farm-system.onrender.com/team/tasks" in text_body


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


def test_send_daily_report_now_translates_per_recipient_language(app, owner):
    """بند إضافي (2026-08-30) — التقرير كان يُبنى مرة واحدة بالعربي
    ويُرسل للجميع بغض النظر عن لغة كل حساب (كود خلفية بلا طلب HTTP،
    فـ`select_locale` يرجع عربي افتراضياً بدون `force_locale` صريح).
    يتأكد هذا الاختبار إن مستخدماً إنجليزياً يستلم فعلياً نسخة إنجليزية،
    ومستخدماً عربياً بنفس الإرسال يستلم نسخة عربية — بمكالمة واحدة."""
    from app.models import Role, User

    owner.email = "owner-ar@example.com"
    role = Role.query.filter_by(name="owner").first()
    en_user = User(name="EN Owner", phone="0500000099", role_id=role.id,
                   language="en", email="owner-en@example.com")
    en_user.set_password("pass1234")
    db.session.add(en_user)
    db.session.commit()

    sent_bodies = {}

    def _fake_notify(user, subject, text_body, html=None):
        sent_bodies[user.email] = (subject, text_body)
        return True

    with patch("app.core.email_service.notify_user", side_effect=_fake_notify):
        sent = send_daily_report_now()

    assert sent == 2
    ar_subject, ar_text = sent_bodies["owner-ar@example.com"]
    en_subject, en_text = sent_bodies["owner-en@example.com"]
    assert "تقرير مراح بو علي" in ar_subject
    assert "القطيع النشط" in ar_text
    assert "Murabi Bu Ali daily report" in en_subject
    assert "Total active herd" in en_text
    assert "القطيع النشط" not in en_text


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
