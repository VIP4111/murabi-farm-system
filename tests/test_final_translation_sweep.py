"""بند إضافي (2026-08-31) — طلبك "اكمل الفحص": مسح منهجي أوسع
(regex عبر كل القوالب + جميع استدعاءات jsonify()) بعد سلسلة دفعات
الترجمة السابقة، بحثاً عن أي نص عربي متبقٍ غير مغلَّف بـ_()."""
from app.extensions import db
from app.models import Role, User


def _make_owner_en(phone="0599999295"):
    role = Role.query.filter_by(name="owner").first()
    user = User(name="Owner EN Nav Test", phone=phone, role_id=role.id, language="en")
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_settings_nav_drawer_translates_for_english_user(app, client):
    """base.html's nav drawer: عنوان مجموعة 'النظام' ورابط 'الإعدادات'
    كانا نصاً عربياً خاماً بدون _() — الوحيدان المتبقيان بين كل عناوين
    مجموعات القائمة الجانبية (بقية العناوين كانت مغلَّفة أصلاً)."""
    owner = _make_owner_en()
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})

    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "System" in body
    assert "Settings" in body
    assert ">النظام<" not in body
    assert ">الإعدادات<" not in body


def test_assistant_send_empty_message_json_error_translates_for_english_user(app, client):
    """app/assistant/routes.py's /assistant/send (مسار JSON): كان يرجّع
    {"error": "الرسالة فاضية"} خاماً بدون _()."""
    owner = _make_owner_en(phone="0599999296")
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})

    resp = client.post("/assistant/send", json={"message": ""})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "The message is empty"
