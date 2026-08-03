"""بند إضافي 113 — اختيار لغة شاشة الدخول (قبل الدخول) صار يُحفظ فعلياً
لحساب المستخدم. قبل هذا البند، الاختيار كان يغيّر شكل شاشة الدخول نفسها
بس، ويُتجاهَل بصمت بعد الدخول الفعلي (select_locale يعطي الأولوية
لـUser.language المحفوظة أصلاً، "ar" افتراضياً)."""
from app.extensions import db


def test_picking_language_before_login_persists_to_account(client, owner):
    assert owner.language == "ar"
    client.post("/login/language", data={"language": "en"})

    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})

    db.session.refresh(owner)
    assert owner.language == "en"


def test_login_without_language_pick_keeps_existing_language(client, owner):
    owner.language = "hi"
    db.session.commit()

    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})

    db.session.refresh(owner)
    assert owner.language == "hi"


def test_invalid_language_pick_ignored(client, owner):
    client.post("/login/language", data={"language": "fr"})
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})

    db.session.refresh(owner)
    assert owner.language == "ar"


def test_failed_login_does_not_change_language(client, owner):
    client.post("/login/language", data={"language": "am"})
    client.post("/login", data={"phone": owner.phone, "password": "wrong-password"})

    db.session.refresh(owner)
    assert owner.language == "ar"
