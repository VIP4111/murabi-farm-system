"""بند إضافي 157 — تأكيد إن توزيع مهمة مباشر وحالة الطوارئ يحاولون
يرسلون إشعار تيليجرام فعلياً (مع mock، بدون شبكة حقيقية بالاختبار)."""
from unittest.mock import patch

from app.extensions import db
from app.team import task_service, report_service
from app.health import health_service
from app.models import Symptom, EmergencySymptom, Role, User
from factories import make_animal, make_barn


def test_assign_task_notifies_assignee_via_telegram(app, owner):
    owner.telegram_chat_id = "555"
    db.session.commit()

    with patch("app.core.telegram_service.notify_user") as mock_notify:
        task_service.assign_task(
            actor=owner, title="مهمة اختبار", assignee_id=owner.id,
        )
    mock_notify.assert_called_once()
    assert mock_notify.call_args[0][0].id == owner.id
    assert "مهمة اختبار" in mock_notify.call_args[0][1]


def test_assign_task_skips_notification_when_no_assignee(app, owner):
    with patch("app.core.telegram_service.notify_user") as mock_notify:
        task_service.assign_task(actor=owner, title="مهمة بلا معيَّن")
    mock_notify.assert_not_called()


def test_emergency_symptom_notifies_users_with_health_manage_permission(app, owner):
    owner.telegram_chat_id = "777"
    db.session.commit()

    make_barn(barn_no="ISO-TG", barn_type="عزل")
    animal = make_animal(animal_no="TG-01")
    symptom = Symptom(name="عرض طوارئ اختبار", is_primary=True)
    db.session.add(symptom)
    db.session.flush()
    db.session.add(EmergencySymptom(
        symptom_id=symptom.id, severity="شديدة", differential="تشخيص تجريبي", advice="راجع الدكتور",
    ))
    db.session.commit()

    with patch("app.core.telegram_service.notify_user") as mock_notify:
        health_service.check_emergency_symptoms(
            animal_id=animal.id, symptom_names=["عرض طوارئ اختبار"], actor_user_id=owner.id,
        )
    assert mock_notify.called
    called_users = [c[0][0].id for c in mock_notify.call_args_list]
    assert owner.id in called_users


def _make_role_user(role_name, phone, telegram_chat_id=None, name="مستخدم اختبار تيليجرام"):
    role = Role.query.filter_by(name=role_name).first()
    user = User(name=name, phone=phone, role_id=role.id,
                language="ar", telegram_chat_id=telegram_chat_id)
    user.set_password("test1234")
    db.session.add(user)
    db.session.commit()
    return user


def _make_worker(phone="0599999150", telegram_chat_id=None):
    return _make_role_user("worker", phone, telegram_chat_id, name="عامل اختبار تيليجرام")


def test_submit_report_notifies_users_with_reports_manage_permission(app, owner):
    owner.telegram_chat_id = "888"
    db.session.commit()
    doctor = _make_role_user("doctor", "0599999151", telegram_chat_id="999", name="دكتور اختبار تيليجرام")
    worker = _make_worker(phone="0599999152", telegram_chat_id="1000")  # مو مدير بلاغات

    with patch("app.core.telegram_service.notify_user") as mock_notify:
        report_service.submit_report(reporter=doctor, description="بلاغ اختبار تيليجرام")
    called_users = [c[0][0].id for c in mock_notify.call_args_list]
    assert owner.id in called_users  # صاحب الحلال يملك reports.manage
    assert doctor.id not in called_users  # نفس صاحب البلاغ ما يحتاج إشعار لنفسه
    assert worker.id not in called_users  # العامل مو مدير بلاغات


def test_transfer_report_notifies_executor_via_telegram(app, owner):
    executor = _make_worker(telegram_chat_id="1010")
    report = report_service.submit_report(reporter=owner, description="بلاغ للتحويل")
    report_service.accept_report(report, actor=owner)

    with patch("app.core.telegram_service.notify_user") as mock_notify:
        report_service.transfer_report(report, actor=owner, executor=executor, note="نفّذ لو سمحت")
    mock_notify.assert_called_once()
    assert mock_notify.call_args[0][0].id == executor.id
    assert "نفّذ لو سمحت" in mock_notify.call_args[0][1]
