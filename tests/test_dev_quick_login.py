"""بند إضافي 123 — دخول سريع بلا كلمة مرور، للتجربة/التطوير بس. موقوف
افتراضياً (ServiceToggle key="dev_quick_login")؛ الفحص الحاسم خادمي —
حتى لو حد عرف رابط /login/quick مباشرة، يُرفض لو الخدمة موقوفة."""
from app.extensions import db
from app.models import Role, User, ServiceToggle


def _toggle(enabled: bool):
    t = ServiceToggle.query.filter_by(key="dev_quick_login").first()
    if not t:
        t = ServiceToggle(key="dev_quick_login", name="تسجيل دخول سريع (وضع تجربة)", is_enabled=enabled)
        db.session.add(t)
    else:
        t.is_enabled = enabled
    db.session.commit()
    return t


def _make_user(phone="0599999123"):
    role = Role.query.filter_by(name="worker").first()
    user = User(name="عامل اختبار دخول سريع", phone=phone, role_id=role.id, language="ar")
    user.set_password("test1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_quick_login_hidden_on_login_page_by_default(app, client):
    resp = client.get("/login")
    assert "auth.quick_login" not in resp.data.decode()
    assert "action=\"/login/quick\"" not in resp.data.decode()


def test_quick_login_rejected_when_toggle_disabled(app, client):
    _toggle(False)
    user = _make_user()
    resp = client.post("/login/quick", data={"user_id": user.id})
    assert resp.status_code == 403


def test_quick_login_shown_and_works_when_toggle_enabled(app, client):
    _toggle(True)
    user = _make_user()
    resp = client.get("/login")
    body = resp.data.decode()
    assert "عامل اختبار دخول سريع" in body

    resp = client.post("/login/quick", data={"user_id": user.id})
    assert resp.status_code == 302
    home = client.get("/")
    assert home.status_code == 200


def test_quick_login_rejected_for_inactive_account_even_when_enabled(app, client):
    _toggle(True)
    user = _make_user()
    user.is_active_account = False
    db.session.commit()
    resp = client.post("/login/quick", data={"user_id": user.id})
    assert resp.status_code == 403
