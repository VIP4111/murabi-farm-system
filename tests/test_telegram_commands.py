"""بند إضافي 160 (المرحلة أ) — أوامر تيليجرام تفاعلية للقراءة السريعة.
يغطي: تحقق التوقيع السري لمسار /telegram/webhook، وتوزيع كل أمر
لصلاحية دوره الصحيحة، والرد المناسب لعضو غير مسجَّل."""
from unittest.mock import patch

from app.extensions import db
from app.core import telegram_commands_service as svc
from app.models import Role, User


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


def test_doctor_only_command_rejected_for_owner(app, owner):
    reply = svc._dispatch("بلاغاتي", owner)
    assert "خاص بالدكتور" in reply


def test_doctor_only_command_allowed_for_doctor(app):
    doctor = _make_role_user("doctor", "0599999162", telegram_chat_id="3")
    reply = svc._dispatch("بلاغاتي", doctor)
    assert "خاص" not in reply


def test_worker_only_command_rejected_for_doctor(app):
    doctor = _make_role_user("doctor", "0599999163", telegram_chat_id="4")
    reply = svc._dispatch("بلاغي_الجديد", doctor)
    assert "خاص بالعامل" in reply


def test_worker_only_command_allowed_for_worker(app):
    worker = _make_role_user("worker", "0599999164", telegram_chat_id="5")
    reply = svc._dispatch("بلاغي_الجديد", worker)
    assert "بلاغ جديد" in reply


def test_unknown_command_lists_available_commands(app, owner):
    reply = svc._dispatch("شي_غير_موجود", owner)
    assert "غير معروف" in reply
