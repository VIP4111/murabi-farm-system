"""إشعارات Push (بند إضافي، طلبك الصريح: "ابيك تصير مثل الواتساب...
يجيني تنبيه والجوال بجيبي"). يغطي:
1. حفظ/حذف اشتراك جهاز عبر /push/subscribe و/push/unsubscribe.
2. مفتاح VAPID العام يرجع 404 لو غير مضبوط، 200 لو مضبوط.
3. /push/test يرسل فعلاً (مع تزييف send_push — بدون اتصال شبكة حقيقي
   بخادم Push خارجي وقت الاختبار).
4. منطق عدم التكرار (`SentPushAlert`) — نفس التنبيه ما يُرسَل مرتين.
"""
from app.core import push_service
from app.extensions import db
from app.models import FarmSettings, PushSubscription, SentPushAlert


def _subscribe(client, endpoint="https://push.example.com/ep1"):
    return client.post("/push/subscribe", json={
        "endpoint": endpoint,
        "keys": {"p256dh": "fake-p256dh", "auth": "fake-auth"},
    })


def test_subscribe_creates_row(logged_in_client, owner):
    resp = _subscribe(logged_in_client)
    assert resp.status_code == 200
    sub = PushSubscription.query.filter_by(endpoint="https://push.example.com/ep1").first()
    assert sub is not None
    assert sub.user_id == owner.id


def test_subscribe_same_endpoint_twice_updates_not_duplicates(logged_in_client, owner):
    _subscribe(logged_in_client)
    _subscribe(logged_in_client)
    count = PushSubscription.query.filter_by(endpoint="https://push.example.com/ep1").count()
    assert count == 1


def test_subscribe_missing_fields_rejected(logged_in_client):
    resp = logged_in_client.post("/push/subscribe", json={"endpoint": "x"})
    assert resp.status_code == 400


def test_unsubscribe_removes_row(logged_in_client, owner):
    _subscribe(logged_in_client)
    resp = logged_in_client.post("/push/unsubscribe", json={"endpoint": "https://push.example.com/ep1"})
    assert resp.status_code == 200
    assert PushSubscription.query.filter_by(endpoint="https://push.example.com/ep1").first() is None


def test_vapid_public_key_404_when_not_configured(logged_in_client, monkeypatch):
    monkeypatch.delenv("VAPID_PUBLIC_KEY_B64URL", raising=False)
    resp = logged_in_client.get("/push/vapid-public-key")
    assert resp.status_code == 404


def test_vapid_public_key_returned_when_configured(logged_in_client, monkeypatch):
    monkeypatch.setenv("VAPID_PUBLIC_KEY_B64URL", "fake-public-key")
    resp = logged_in_client.get("/push/vapid-public-key")
    assert resp.status_code == 200
    assert resp.get_json()["public_key"] == "fake-public-key"


def test_push_test_without_subscription_fails(logged_in_client):
    resp = logged_in_client.post("/push/test")
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "no_subscription"


def test_push_test_sends_via_fake_subscription(logged_in_client, monkeypatch):
    _subscribe(logged_in_client)
    monkeypatch.setattr(push_service, "send_push", lambda sub, payload: True)
    resp = logged_in_client.post("/push/test")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["sent"] == 1


def test_send_push_treats_vapid_key_mismatch_as_invalid_subscription(monkeypatch):
    """إصلاح — بلاغ مستخدم حقيقي بعد تدوير مفاتيح VAPID: اشتراك بمفتاح
    عام قديم يفشل بصمت بخطأ "VapidPkHashMismatch" (400) من خادم الدفع
    — نفس فئة اشتراك منتهي/ملغى (404/410)، يرجع False بدل ما يرفع
    الاستثناء، عشان الطرف المستدعي يحذف الاشتراك الميت بدل ما يعيد
    محاولته للأبد."""
    from pywebpush import WebPushException

    class FakeResponse:
        status_code = 400
        text = '{"reason":"VapidPkHashMismatch"}'

    def fake_webpush(**kwargs):
        raise WebPushException("Push failed: 400 Bad Request", response=FakeResponse())

    monkeypatch.setenv("VAPID_PRIVATE_KEY_B64URL", "fake-private-key")
    monkeypatch.setenv("VAPID_PUBLIC_KEY_B64URL", "fake-public-key")
    monkeypatch.setattr(push_service, "webpush", fake_webpush)

    class FakeSub:
        endpoint = "https://push.example.com/x"
        p256dh = "p"
        auth = "a"

    result = push_service.send_push(FakeSub(), {"title": "t", "body": "b"})
    assert result is False


def test_alert_check_does_not_resend_same_alert_twice(app, owner, monkeypatch):
    """نفس التنبيه (alert_key ثابت) ما يُرسَل مرتين — لولا `SentPushAlert`
    كل فحص دوري كان يرسل كل التنبيهات النشطة من جديد."""
    from app.core import alerts_service

    sub = PushSubscription(user_id=owner.id, endpoint="https://push.example.com/ep-alert",
                            p256dh="p", auth="a")
    db.session.add(sub)
    db.session.commit()

    fake_alert = {
        "category_key": "vaccination_due", "category": "تحصين", "icon": "💉",
        "label": "A-01 — لقاح اختبار", "detail": "", "urgent": True,
        "animal_id": None, "barn_id": None,
    }
    monkeypatch.setattr(alerts_service, "get_alerts_for_user", lambda user: [fake_alert])
    sent_calls = []
    monkeypatch.setattr(push_service, "send_push", lambda s, payload: sent_calls.append(payload) or True)
    monkeypatch.setattr(push_service, "vapid_configured", lambda: True)

    # `alert_action_url` يستخدم `url_for` — يحتاج سياق طلب فعلي، تماماً
    # زي وقت التشغيل الحقيقي (الدالة تُستدعى من `before_request`، دايماً
    # جوا طلب حقيقي هناك).
    with app.test_request_context("/"):
        push_service.check_and_send_alert_push_notifications()
    assert len(sent_calls) == 1
    assert SentPushAlert.query.filter_by(user_id=owner.id).count() == 1

    # نفرض الحارس الزمني منتهي عشان الفحص الثاني يشتغل فوراً (مو ينتظر 15 دقيقة)
    FarmSettings.get().last_push_alert_check = None
    db.session.commit()
    with app.test_request_context("/"):
        push_service.check_and_send_alert_push_notifications()
    assert len(sent_calls) == 1, "نفس التنبيه ما لازم يُرسَل مرة ثانية"
