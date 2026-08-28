"""بند إضافي 160 (المرحلة أ) — أوامر تيليجرام تفاعلية للقراءة السريعة.
يغطي: تحقق التوقيع السري لمسار /telegram/webhook، وتوزيع كل أمر
لصلاحية دوره الصحيحة، والرد المناسب لعضو غير مسجَّل."""
from unittest.mock import patch

from app.extensions import db
from app.core import telegram_commands_service as svc
from app.models import Role, User, Task, Report, Permission
from app.team import report_service, task_service


def _make_role_user(role_name, phone, telegram_chat_id=None):
    role = Role.query.filter_by(name=role_name).first()
    user = User(name=f"مستخدم {role_name}", phone=phone, role_id=role.id,
                language="ar", telegram_chat_id=telegram_chat_id)
    user.set_password("test1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_webhook_rejects_request_without_valid_secret(app, client):
    resp = client.post("/telegram/webhook", json={"message": {"chat": {"id": 1}, "text": "/مهامي"}})
    assert resp.status_code == 403


def test_webhook_accepts_request_with_valid_secret(app, client, owner):
    owner.telegram_chat_id = "42"
    db.session.commit()
    with patch("app.core.telegram_service.webhook_secret", return_value="s3cr3t"), \
         patch("app.core.telegram_service.send_message") as mock_send:
        resp = client.post(
            "/telegram/webhook",
            json={"message": {"chat": {"id": 42}, "text": "/مهامي"}},
            headers={"X-Telegram-Bot-Api-Secret-Token": "s3cr3t"},
        )
    assert resp.status_code == 200
    mock_send.assert_called_once()


def test_unregistered_chat_id_gets_explanation(app):
    reply_holder = {}

    def _capture(chat_id, text):
        reply_holder["text"] = text
        return True

    with patch("app.core.telegram_service.send_message", side_effect=_capture):
        svc.handle_update({"message": {"chat": {"id": 999}, "text": "/مهامي"}})
    assert "غير مرتبط" in reply_holder["text"]


def test_my_tasks_command_available_to_any_role(app):
    worker = _make_role_user("worker", "0599999160", telegram_chat_id="1")
    reply = svc._dispatch("مهامي", worker)
    assert "مهام" in reply


def test_owner_only_command_rejected_for_worker(app):
    worker = _make_role_user("worker", "0599999161", telegram_chat_id="2")
    reply = svc._dispatch("تنبيهات", worker)
    assert "خاص بصاحب الحلال" in reply


def test_owner_only_command_allowed_for_owner(app, owner):
    reply = svc._dispatch("تنبيهات", owner)
    assert "خاص" not in reply


def test_doctor_command_allowed_for_owner(app, owner):
    """بند إضافي 294 — الفحص صار بصلاحية `health.view` بدل اسم الدور
    الحرفي "doctor"؛ صاحب الحلال يملك كل الصلاحيات أصلاً (بما فيها
    health.view)، فيقدر يستخدم أوامر الدكتور كمان — سلوك متوقّع
    ومنطقي بنظام مبني على الصلاحيات، عكس التقييد الحرفي القديم."""
    reply = svc._dispatch("بلاغاتي", owner)
    assert "صلاحية عرض السجل الصحي" not in reply


def test_doctor_only_command_rejected_for_worker_without_health_permission(app):
    worker = _make_role_user("worker", "0599999165", telegram_chat_id="6")
    reply = svc._dispatch("بلاغاتي", worker)
    assert "صلاحية عرض السجل الصحي" in reply


def test_doctor_only_command_allowed_for_doctor(app):
    doctor = _make_role_user("doctor", "0599999162", telegram_chat_id="3")
    reply = svc._dispatch("بلاغاتي", doctor)
    assert "خاص" not in reply


def test_worker_only_command_rejected_for_doctor(app):
    """بند إضافي 294 — الدكتور الافتراضي ما عنده صلاحية `reports.submit`
    أصلاً، فيُرفض — بس بالرسالة الجديدة المبنية على الصلاحية، مو اسم
    الدور الحرفي."""
    doctor = _make_role_user("doctor", "0599999163", telegram_chat_id="4")
    reply = svc._dispatch("بلاغي_الجديد", doctor)
    assert "صلاحية رفع بلاغ" in reply


def test_custom_role_with_reports_submit_permission_can_use_worker_command(app):
    """أهم اختبار — نفس فجوة "المزارع" اللي بدأنا منها: دور مخصَّص
    مستنسخ من صلاحيات العامل (فيه `reports.submit`) يقدر يستخدم
    `/بلاغي_الجديد` رغم إن اسمه مو "worker" حرفياً."""
    from app.extensions import db
    from app.models import Role, Permission, User

    perm = Permission.query.filter_by(code="reports.submit").first()
    role = Role(name="المزارع", display_name="المزارع", is_system=False)
    role.permissions = [perm]
    db.session.add(role)
    db.session.commit()

    farmer = User(name="مزارع اختبار", phone="0599999166", role_id=role.id,
                  telegram_chat_id="7")
    farmer.set_password("pass1234")
    db.session.add(farmer)
    db.session.commit()

    reply = svc._dispatch("بلاغي_الجديد", farmer)
    assert "صلاحية رفع بلاغ" not in reply


def test_worker_only_command_allowed_for_worker(app):
    worker = _make_role_user("worker", "0599999164", telegram_chat_id="5")
    reply = svc._dispatch("بلاغي_الجديد", worker)
    assert "بلاغ جديد" in reply


def test_unknown_command_lists_available_commands(app, owner):
    reply = svc._dispatch("شي_غير_موجود", owner)
    assert "غير معروف" in reply


def test_duplicate_update_id_handled_once_only(app, owner):
    owner.telegram_chat_id = "77"
    db.session.commit()
    update = {"update_id": 555, "message": {"chat": {"id": 77}, "text": "/مهامي"}}
    with patch("app.core.telegram_service.send_message") as mock_send:
        svc.handle_update(update)
        svc.handle_update(update)  # نفس النبضة، تكرار (إعادة إرسال تيليجرام)
    mock_send.assert_called_once()


# ---- المرحلة ب: أوامر تحكم فعلي ----

def test_accept_report_command_by_owner(app, owner):
    report = report_service.submit_report(reporter=owner, description="بلاغ اختبار قبول")
    reply = svc._dispatch(f"/قبول {report.id}", owner)
    assert "تم قبول" in reply
    db.session.refresh(report)
    assert report.status == "accepted"


def test_accept_report_command_rejects_worker_without_permission(app):
    worker = _make_role_user("worker", "0599999170", telegram_chat_id="10")
    report = report_service.submit_report(reporter=worker, description="بلاغ اختبار 2")
    reply = svc._dispatch(f"/قبول {report.id}", worker)
    assert "صلاحية" in reply
    db.session.refresh(report)
    assert report.status == "new"


def test_close_report_command_by_manager(app, owner):
    report = report_service.submit_report(reporter=owner, description="بلاغ اختبار إغلاق")
    report_service.accept_report(report, actor=owner)
    reply = svc._dispatch(f"/إغلاق {report.id}", owner)
    assert "تم إغلاق" in reply
    db.session.refresh(report)
    assert report.status == "closed"


def test_close_report_command_rejects_non_manager(app):
    owner_user = _make_role_user("owner", "0599999171")
    worker = _make_role_user("worker", "0599999172", telegram_chat_id="11")
    report = report_service.submit_report(reporter=worker, description="بلاغ اختبار إغلاق 2")
    report_service.accept_report(report, actor=owner_user)
    reply = svc._dispatch(f"/إغلاق {report.id}", worker)
    assert "⚠️" in reply
    db.session.refresh(report)
    assert report.status == "accepted"


def test_assign_task_command_by_owner(app, owner):
    worker = _make_role_user("worker", "0599999173", telegram_chat_id="12")
    reply = svc._dispatch(f"/مهمة {worker.phone} نظّف الحظيرة الشمالية", owner)
    assert "تم توزيع مهمة" in reply
    task = Task.query.filter_by(assignee_id=worker.id).first()
    assert task is not None
    assert task.title == "نظّف الحظيرة الشمالية"


def test_assign_task_command_unknown_phone(app, owner):
    reply = svc._dispatch("/مهمة 0500000999 مهمة وهمية", owner)
    assert "لا يوجد عضو" in reply


def test_mark_done_completes_most_recent_open_task(app, owner):
    worker = _make_role_user("worker", "0599999174", telegram_chat_id="13")
    task_service.assign_task(actor=owner, title="مهمة تجريبية", assignee_id=worker.id)
    reply = svc._dispatch("تم", worker)
    assert "تم إنجاز المهمة" in reply
    task = Task.query.filter_by(assignee_id=worker.id).first()
    assert task.status == "done"


def test_mark_done_with_nothing_open_returns_clear_message(app):
    worker = _make_role_user("worker", "0599999175", telegram_chat_id="14")
    reply = svc._dispatch("تم", worker)
    assert "ما فيه مهمة أو بلاغ" in reply
