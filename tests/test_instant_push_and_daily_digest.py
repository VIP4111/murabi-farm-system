"""ميزات إشعارات Push إضافية (بند إضافي، طلبك بعد تفعيل الميزة
الأساسية): 1) إشعار فوري لمهمة/بلاغ معيّن للمستخدم شخصياً، 2) ملخص
يومي واحد بإشعار."""
from app.core import push_service
from app.extensions import db
from app.models import PushSubscription, Role, User


def _make_worker(phone="0500009001"):
    role = Role.query.filter_by(name="worker").first()
    worker = User(name="عامل اختبار الإشعارات", phone=phone, role_id=role.id, language="ar")
    worker.set_password("pass1234")
    db.session.add(worker)
    db.session.commit()
    return worker


def _subscribe(user):
    sub = PushSubscription(user_id=user.id, endpoint=f"https://push.example.com/{user.id}",
                            p256dh="p", auth="a")
    db.session.add(sub)
    db.session.commit()
    return sub


def test_assign_task_sends_instant_push_to_assignee(app, owner, monkeypatch):
    from app.team.task_service import assign_task

    worker = _make_worker()
    _subscribe(worker)
    calls = []
    monkeypatch.setattr(push_service, "send_push", lambda sub, payload: calls.append(payload) or True)
    monkeypatch.setattr(push_service, "vapid_configured", lambda: True)

    assign_task(actor=owner, title="مهمة اختبار الإشعار الفوري", assignee_id=worker.id)

    assert len(calls) == 1
    assert "مهمة" in calls[0]["title"] or "مهمة" in calls[0]["body"]


def test_transfer_report_sends_instant_push_to_executor(app, owner, monkeypatch):
    from app.team.report_service import submit_report, accept_report, transfer_report

    executor = _make_worker(phone="0500009002")
    _subscribe(executor)
    calls = []
    monkeypatch.setattr(push_service, "send_push", lambda sub, payload: calls.append(payload) or True)
    monkeypatch.setattr(push_service, "vapid_configured", lambda: True)

    report = submit_report(reporter=executor, description="بلاغ اختبار")
    calls.clear()  # نتجاهل إشعار "بلاغ جديد" للمدراء، نركّز على القبول والتحويل
    accept_report(report, actor=owner)
    transfer_report(report, actor=owner, executor=executor, note="نفّذ من فضلك")

    # بند إصلاح (فحص شامل سطر بسطر — ميزة البلاغات) — صار مقدّم البلاغ
    # (هنا نفس الشخص المنفّذ لاحقاً) يستلم إشعار قبول أيضاً، فوق إشعار
    # التحويل الأصلي — 2 بدل 1.
    assert len(calls) == 2
    assert "استلام" in calls[0]["title"]
    assert "بلاغ" in calls[1]["title"]


def test_push_test_digest_endpoint_sends_immediately(logged_in_client, owner, monkeypatch):
    """زر "إرسال ملخص تجريبي الآن" بشاشة الإعدادات (بند إضافي، طلبك:
    "نعم ظيفها") — يرسل فوراً بدون انتظار دورة اليوم التالي ولا فحص
    صلاحية reports.manage (اختبار تقني بس، الزر نفسه محمي أصلاً)."""
    _subscribe(owner)
    calls = []
    monkeypatch.setattr(push_service, "send_push", lambda sub, payload: calls.append(payload) or True)
    monkeypatch.setattr(push_service, "vapid_configured", lambda: True)

    resp = logged_in_client.post("/push/test-digest")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    assert len(calls) == 1
    assert "ملخص" in calls[0]["title"]


def test_push_test_digest_endpoint_without_subscription_fails(logged_in_client):
    resp = logged_in_client.post("/push/test-digest")
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "no_subscription"


def test_daily_push_digest_sent_once_per_day(app, owner, monkeypatch):
    from app.core import daily_push_report_service
    from app.models import FarmSettings

    _subscribe(owner)
    calls = []
    monkeypatch.setattr(push_service, "send_push", lambda sub, payload: calls.append(payload) or True)
    monkeypatch.setattr(push_service, "vapid_configured", lambda: True)

    daily_push_report_service.generate_daily_push_report_if_needed()
    assert len(calls) == 1
    assert "ملخص" in calls[0]["title"]

    # نفس اليوم — ما يُرسَل مرة ثانية
    daily_push_report_service.generate_daily_push_report_if_needed()
    assert len(calls) == 1

    # يوم جديد (نفرض الحارس منتهي) — يُرسَل من جديد
    FarmSettings.get().last_daily_push_report_sent = None
    db.session.commit()
    daily_push_report_service.generate_daily_push_report_if_needed()
    assert len(calls) == 2
