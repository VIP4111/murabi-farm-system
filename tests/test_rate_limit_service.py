"""بند إضافي 119 — تحديد معدل الطلبات (آخر نقطة من التحليل الأمني
الثالث). قبل هذا البند، ما فيه أي حد على البلاغات أو رفع الملفات —
حساب واحد يقدر يرسل عدد غير محدود بلا أي كبح."""
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import RateLimitHit
from app.core.rate_limit_service import check_and_record, RateLimitExceeded


def test_allows_calls_under_the_limit(app, owner):
    for _ in range(3):
        check_and_record(user_id=owner.id, key="test_key", max_calls=3, window_seconds=60)
    assert RateLimitHit.query.filter_by(user_id=owner.id, key="test_key").count() == 3


def test_blocks_call_over_the_limit(app, owner):
    for _ in range(3):
        check_and_record(user_id=owner.id, key="test_key2", max_calls=3, window_seconds=60)
    try:
        check_and_record(user_id=owner.id, key="test_key2", max_calls=3, window_seconds=60)
        assert False, "المفروض يرفع RateLimitExceeded"
    except RateLimitExceeded as e:
        assert e.retry_after_seconds > 0
    # المحاولة المرفوضة ما تُحتسب — العدد يبقى 3
    assert RateLimitHit.query.filter_by(user_id=owner.id, key="test_key2").count() == 3


def test_old_hits_outside_window_do_not_count(app, owner):
    old_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=120)
    for _ in range(3):
        db.session.add(RateLimitHit(user_id=owner.id, key="test_key3", created_at=old_time))
    db.session.commit()

    check_and_record(user_id=owner.id, key="test_key3", max_calls=3, window_seconds=60)
    remaining = RateLimitHit.query.filter_by(user_id=owner.id, key="test_key3").count()
    assert remaining == 1  # القديمة انحذفت، وحدة جديدة انسجّلت


def test_different_keys_are_independent(app, owner):
    for _ in range(3):
        check_and_record(user_id=owner.id, key="key_a", max_calls=3, window_seconds=60)
    check_and_record(user_id=owner.id, key="key_b", max_calls=3, window_seconds=60)
    assert RateLimitHit.query.filter_by(user_id=owner.id, key="key_b").count() == 1


def test_report_submit_route_enforces_limit(app, logged_in_client):
    from factories import make_animal
    animal = make_animal(animal_no="RL-01")
    for i in range(10):
        resp = logged_in_client.post("/team/reports/new", data={
            "animal_id": str(animal.id), "description": f"بلاغ اختبار {i}",
        })
        assert resp.status_code == 302

    blocked = logged_in_client.post("/team/reports/new", data={
        "animal_id": str(animal.id), "description": "بلاغ اختبار 11",
    }, follow_redirects=True)
    assert "بلاغات كثيرة" in blocked.data.decode()


def test_assistant_send_route_enforces_limit(app, logged_in_client):
    for i in range(30):
        resp = logged_in_client.post("/assistant/send", json={"message": f"سؤال {i}"})
        assert resp.status_code == 200

    blocked = logged_in_client.post("/assistant/send", json={"message": "سؤال 31"})
    assert blocked.status_code == 429


def test_farm_notes_new_route_enforces_limit(app, logged_in_client):
    """بند إضافي 314 — نفس فئة فجوة بند 313: كل ملاحظة جديدة تستدعي
    Gemini فعلياً (embed_text عبر create_note)، بس المسار كان بلا حد."""
    for i in range(20):
        resp = logged_in_client.post("/assistant/farm-notes/new", data={"body": f"ملاحظة {i}"})
        assert resp.status_code == 302

    blocked = logged_in_client.post("/assistant/farm-notes/new", data={"body": "ملاحظة 21"}, follow_redirects=True)
    assert "طلبات كثيرة" in blocked.data.decode()


def test_animal_checkup_suggest_route_enforces_limit(app, logged_in_client):
    """بند إضافي 313 — فجوة تدقيق حقيقية: كانت الوحيدة بين كل مسارات
    استدعاء Gemini بالمشروع بدون أي حد لمعدل الطلبات (ثغرة استنزاف حصة/
    تكلفة API)."""
    from factories import make_animal
    animal = make_animal(animal_no="950")

    for i in range(20):
        resp = logged_in_client.post(f"/animals/{animal.id}/checkup-suggest")
        assert resp.status_code == 302

    blocked = logged_in_client.post(f"/animals/{animal.id}/checkup-suggest", follow_redirects=True)
    assert "طلبات كثيرة" in blocked.data.decode()
