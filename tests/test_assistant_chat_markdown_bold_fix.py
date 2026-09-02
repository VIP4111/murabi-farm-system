"""بند إصلاح: المستخدم أرسل صورة شاشة توضح إن ردود المساعد الذكي كانت
تظهر فيها **نجوم** ماركداون حرفياً بدل تنسيق عريض (النماذج أحياناً
تخالف تعليمة النظام بعدم استخدام ماركداون). الإصلاح: فلتر `chat_format`
يهرّب الـHTML ثم يحوّل **نص** لـ<strong> حقيقي عند عرض سجل المحادثة."""
from app import create_app
from app.models import AssistantMessage
from app.extensions import db


def test_chat_format_filter_converts_double_asterisk_to_strong():
    app = create_app()
    with app.app_context():
        filt = app.jinja_env.filters["chat_format"]
        result = str(filt("جرّب **قسم التحصينات** من القائمة"))
        assert "<strong>قسم التحصينات</strong>" in result
        assert "**" not in result


def test_chat_format_filter_escapes_html_injection():
    app = create_app()
    with app.app_context():
        filt = app.jinja_env.filters["chat_format"]
        result = str(filt("<script>alert(1)</script> **مهم**"))
        assert "<script>" not in result
        assert "&lt;script&gt;" in result
        assert "<strong>مهم</strong>" in result


def test_chat_page_renders_message_bold_not_raw_asterisks(app, logged_in_client, owner):
    with app.app_context():
        db.session.add(AssistantMessage(
            user_id=owner.id, role="assistant",
            content="1. **قسم التحصينات** من القائمة الرئيسية",
        ))
        db.session.commit()

    resp = logged_in_client.get("/assistant/")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert "<strong>قسم التحصينات</strong>" in body
