"""تفضيلات إشعارات Push الشخصية (بند إضافي، طلبك: "نخلي اختيار
التنبيهات المراقَب فيها عن طريق الإعدادات") — كل مستخدم يختار لنفسه
أنواع التنبيهات اللي يبيها Push، بدون صلاحية خاصة."""
from app.core import alerts_service, push_service
from app.extensions import db
from app.models import FarmSettings, PushSubscription, SentPushAlert


def test_push_preferences_page_loads_for_any_logged_in_user(logged_in_client):
    resp = logged_in_client.get("/push/preferences")
    assert resp.status_code == 200
    assert "تفضيلات إشعارات Push".encode() in resp.data


def test_saving_preferences_persists_muted_categories(logged_in_client, owner):
    all_keys = [k for k, _label in alerts_service.alert_category_choices()]
    keep_enabled = all_keys[:3]
    resp = logged_in_client.post("/push/preferences", data={"enabled_categories": keep_enabled})
    assert resp.status_code == 302
    muted = owner.muted_push_categories()
    assert set(all_keys[3:]) == muted
    for k in keep_enabled:
        assert k not in muted


def test_enabling_all_categories_clears_muted_field(logged_in_client, owner):
    owner.push_muted_categories = "vaccination_due,near_birth"
    db.session.commit()
    all_keys = [k for k, _label in alerts_service.alert_category_choices()]
    logged_in_client.post("/push/preferences", data={"enabled_categories": all_keys})
    assert owner.muted_push_categories() == set()
    assert owner.push_muted_categories is None


def test_muted_category_alert_is_never_sent_as_push(app, owner, monkeypatch):
    """نفس اختبار عدم التكرار السابق (test_push_notifications.py) بس
    هنا نتأكد إن التنبيه المكتوم أصلاً ما يوصل الطرف اللي يرسل —
    ولا حتى يُسجَّل كـ"مُرسَل" (عشان لو المستخدم فعّله لاحقاً، يوصله
    التنبيه وقتها عادي، مو مكتوم للأبد بالغلط)."""
    owner.push_muted_categories = "vaccination_due"
    db.session.commit()

    sub = PushSubscription(user_id=owner.id, endpoint="https://push.example.com/muted-test",
                            p256dh="p", auth="a")
    db.session.add(sub)
    db.session.commit()

    muted_alert = {
        "category_key": "vaccination_due", "category": "تحصين", "icon": "💉",
        "label": "A-01 — لقاح اختبار", "detail": "", "urgent": True,
        "animal_id": None, "barn_id": None,
    }
    monkeypatch.setattr(alerts_service, "get_alerts_for_user", lambda user: [muted_alert])
    sent_calls = []
    monkeypatch.setattr(push_service, "send_push", lambda s, payload: sent_calls.append(payload) or True)
    monkeypatch.setattr(push_service, "vapid_configured", lambda: True)

    with app.test_request_context("/"):
        push_service.check_and_send_alert_push_notifications()

    assert sent_calls == []
    assert SentPushAlert.query.filter_by(user_id=owner.id).count() == 0
