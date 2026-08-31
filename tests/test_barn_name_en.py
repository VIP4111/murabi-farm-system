"""بند إضافي (2026-08-31) — طلبك الصريح بعد ما لاحظت اسم الحظيرة
(بيانات حرة كتبها المستخدم) يبقى عربياً بشاشة دكتور إنجليزي، رغم
ترجمة كل النص النظامي حولها ("Barn without a responsible worker"،
"no responsible worker"...). حقل اختياري ثانٍ (`Barn.barn_name_en`)
يكتبه صاحب الحلال بنفسه — لو فاضي، يبقى السلوك القديم (الاسم العربي
يظهر للجميع) كما هو بدون كسر."""
from app.extensions import db
from app.models import Role, User
from factories import make_barn


def _make_doctor_en(phone="0599999290"):
    role = Role.query.filter_by(name="doctor").first()
    user = User(name="Dr EN Barn Test", phone=phone, role_id=role.id, language="en")
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_display_name_falls_back_to_arabic_without_english_name(app):
    barn = make_barn(barn_no="BN-01", barn_name="حظيرة العزل")
    assert barn.display_name() == "حظيرة العزل"  # لغة افتراضية عربي خارج سياق طلب


def test_display_name_uses_english_name_for_english_user(app, client):
    barn = make_barn(barn_no="BN-02", barn_name="حظيرة العزل للمستجدين")
    barn.barn_name_en = "New Arrivals Isolation Barn"
    db.session.commit()
    doctor = _make_doctor_en()
    client.post("/login", data={"phone": doctor.phone, "password": "pass1234"})

    resp = client.get("/alerts")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "New Arrivals Isolation Barn" in body
    assert "حظيرة العزل للمستجدين" not in body


def test_display_name_stays_arabic_without_english_name_set(app, client):
    """لو ما فيه اسم إنجليزي مسجَّل، الاسم العربي يبقى يظهر حتى للمستخدم
    الإنجليزي — سلوك السابق محفوظ بدون كسر."""
    make_barn(barn_no="BN-03", barn_name="حظيرة بدون اسم إنجليزي")
    doctor = _make_doctor_en(phone="0599999291")
    client.post("/login", data={"phone": doctor.phone, "password": "pass1234"})

    resp = client.get("/alerts")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "حظيرة بدون اسم إنجليزي" in body


def test_barn_edit_form_saves_english_name(app, client, owner):
    barn = make_barn(barn_no="BN-04", barn_name="حظيرة رقم أربعة")
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})

    resp = client.post(f"/barns/{barn.id}/edit", data={
        "barn_no": barn.barn_no, "barn_name": barn.barn_name,
        "barn_name_en": "Barn Four", "barn_type": "عادية",
    }, follow_redirects=True)
    assert resp.status_code == 200

    db.session.refresh(barn)
    assert barn.barn_name_en == "Barn Four"
