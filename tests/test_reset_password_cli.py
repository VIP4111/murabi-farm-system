"""بند إضافي 88 — أمر `flask reset-password` (نقطة 3 من التحليل الثاني).
النظام ما فيه بريد إلكتروني، فالاسترجاع الذاتي عبر إيميل غير ممكن —
هذا البديل العملي: أمر تحكم يُشغَّل من تبويب Shell بلوحة Render."""
from app.extensions import db
from app.models import User


def test_reset_password_changes_hash_and_allows_login(app, owner):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["reset-password", owner.phone, "new-strong-pass"])
    assert "بنجاح" in result.output

    db.session.refresh(owner)
    assert owner.check_password("new-strong-pass") is True
    assert owner.check_password("pass1234") is False


def test_reset_password_clears_existing_lockout(app, owner):
    owner.failed_login_attempts = 5
    from datetime import datetime, timedelta, timezone
    owner.locked_until = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=15)
    db.session.commit()

    runner = app.test_cli_runner()
    runner.invoke(args=["reset-password", owner.phone, "new-strong-pass"])

    db.session.refresh(owner)
    assert owner.failed_login_attempts == 0
    assert owner.locked_until is None


def test_reset_password_unknown_phone_does_not_crash(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["reset-password", "0599999999", "whatever"])
    assert "ما فيه حساب" in result.output
