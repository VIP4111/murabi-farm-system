"""فحص شامل سطر بسطر — ميزة البلاغات (دورة الحياة كاملة).

فجوة UX حقيقية اكتُشفت: مقدّم البلاغ ما كان يوصله أي إشعار عند قبول
بلاغه أو تأجيله أو إغلاقه — submit_report/transfer_report فقط كانا
يشعّران الطرف المعني فوراً، بينما accept/postpone/close كانت صامتة
تماماً، فيضطر مقدّم البلاغ يفتح التطبيق ويشيّك يدوياً باستمرار."""
from unittest.mock import patch

from app.extensions import db
from app.models import Role, User
from app.team import report_service


def _make_user(name, phone, permission_role="worker"):
    role = Role.query.filter_by(name=permission_role).first()
    user = User(name=name, phone=phone, role_id=role.id, language="ar", is_active_account=True)
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_accept_report_notifies_the_original_reporter(app):
    reporter = _make_user("مبلّغ", "0599999400")
    manager = _make_user("مدير", "0599999401", permission_role="owner")
    report = report_service.submit_report(reporter=reporter, description="بلاغ اختبار")

    with patch("app.core.push_service.notify_user") as mock_notify:
        report_service.accept_report(report, actor=manager)

    assert mock_notify.called, "مقدّم البلاغ لازم يوصله إشعار عند قبول بلاغه"
    notified_user = mock_notify.call_args[0][0]
    assert notified_user.id == reporter.id


def test_close_report_notifies_the_original_reporter(app):
    reporter = _make_user("مبلّغ", "0599999402")
    manager = _make_user("مدير", "0599999403", permission_role="owner")
    report = report_service.submit_report(reporter=reporter, description="بلاغ اختبار")
    report_service.accept_report(report, actor=manager)

    with patch("app.core.push_service.notify_user") as mock_notify:
        report_service.close_report(report, actor=manager, note="تم الحل")

    assert mock_notify.called, "مقدّم البلاغ لازم يوصله إشعار عند إغلاق بلاغه"
    notified_user = mock_notify.call_args[0][0]
    assert notified_user.id == reporter.id


def test_postpone_report_notifies_the_original_reporter(app):
    reporter = _make_user("مبلّغ", "0599999404")
    manager = _make_user("مدير", "0599999405", permission_role="owner")
    report = report_service.submit_report(reporter=reporter, description="بلاغ اختبار")

    with patch("app.core.push_service.notify_user") as mock_notify:
        report_service.postpone_report(report, actor=manager, reason="ننتظر توفر قطعة غيار")

    assert mock_notify.called, "مقدّم البلاغ لازم يوصله إشعار عند تأجيل بلاغه"
    notified_user = mock_notify.call_args[0][0]
    assert notified_user.id == reporter.id


def test_no_self_notification_when_actor_is_the_reporter(app):
    """حالة نادرة: نفس الشخص مبلّغ ومدير (صلاحية reports.manage) —
    ما يستاهل يشعّر نفسه."""
    owner_reporter = _make_user("صاحب مبلّغ", "0599999406", permission_role="owner")
    report = report_service.submit_report(reporter=owner_reporter, description="بلاغ اختبار")

    with patch("app.core.push_service.notify_user") as mock_notify:
        report_service.accept_report(report, actor=owner_reporter)

    assert not mock_notify.called, "ما يصير المستخدم يشعّر نفسه"
