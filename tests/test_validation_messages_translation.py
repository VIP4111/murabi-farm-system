"""بند إضافي (2026-08-30) — استكمال جولة الترجمة: رسائل ValueError
اللي ترتفع من خدمات النظام (validation_service وغيرها) وتُعرض عبر
`flash(str(e), "error")` بالراوتات — الترجمة الصحيحة تصير عند مصدر
الرفع (`raise ValueError(_("..."))`) مو عند نقطة العرض، لأن `str(e)`
يجمّد النص وقت الرفع."""
from app.extensions import db
from app.models import Role, User
from factories import make_barn


def _make_owner_en(phone="0599999270"):
    role = Role.query.filter_by(name="owner").first()
    user = User(name="Owner EN Test", phone=phone, role_id=role.id, language="en")
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_animal_creation_negative_price_error_translates_for_english_user(app, client):
    barn = make_barn(barn_no="VAL-01")
    owner = _make_owner_en()
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})

    resp = client.post("/animals/new", data={
        "animal_no": "VAL-ANIMAL-1", "source": "purchase", "gender": "أنثى",
        "barn_id": str(barn.id), "color": "أبيض", "price": "-50",
    }, follow_redirects=True)
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "ما يقدر يكون رقماً سالباً" not in body
    assert "Price can" in body and "negative number" in body


def test_unrealistic_weight_error_translates_for_english_user(app, client):
    barn = make_barn(barn_no="VAL-02")
    owner = _make_owner_en(phone="0599999271")
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})

    resp = client.post("/animals/new", data={
        "animal_no": "VAL-ANIMAL-2", "source": "purchase", "gender": "أنثى",
        "barn_id": str(barn.id), "color": "أبيض", "weight": "9999",
    }, follow_redirects=True)
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "غير منطقي" not in body
    assert "unrealistic" in body
