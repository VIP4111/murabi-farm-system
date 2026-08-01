"""بند إضافي 86 — قفل بعد محاولات دخول فاشلة متكررة (نقطة أمنية جديدة
من التحليل الثاني). قبل هذا البند ما كان فيه أي حد لعدد المحاولات."""
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import User


def _fail_login(client, phone, password="wrong-password"):
    return client.post("/login", data={"phone": phone, "password": password})


def test_account_locks_after_five_failed_attempts(client, owner):
    for _ in range(User.LOCKOUT_THRESHOLD):
        _fail_login(client, owner.phone)

    db.session.refresh(owner)
    assert owner.failed_login_attempts == User.LOCKOUT_THRESHOLD
    assert owner.is_locked() is True


def test_locked_account_rejects_even_correct_password(client, owner):
    for _ in range(User.LOCKOUT_THRESHOLD):
        _fail_login(client, owner.phone)

    resp = client.post("/login", data={"phone": owner.phone, "password": "pass1234"}, follow_redirects=True)
    assert "مقفل مؤقتاً".encode() in resp.data
    # ما سُجّل دخول فعلياً
    resp2 = client.get("/team/members")
    assert resp2.status_code in (302, 403)


def test_successful_login_resets_failed_counter(client, owner):
    _fail_login(client, owner.phone)
    _fail_login(client, owner.phone)
    db.session.refresh(owner)
    assert owner.failed_login_attempts == 2

    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    db.session.refresh(owner)
    assert owner.failed_login_attempts == 0
    assert owner.locked_until is None


def test_lockout_expires_after_window(client, owner):
    owner.failed_login_attempts = User.LOCKOUT_THRESHOLD
    owner.locked_until = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)  # القفل انتهى فعلاً
    db.session.commit()

    resp = client.post("/login", data={"phone": owner.phone, "password": "pass1234"}, follow_redirects=False)
    assert resp.status_code == 302  # دخول ناجح


def test_unknown_phone_number_does_not_error(client):
    resp = _fail_login(client, "0599999999")
    assert resp.status_code == 200
