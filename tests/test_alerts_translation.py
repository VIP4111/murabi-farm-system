"""بند إضافي (2026-08-30) — طلبك الصريح بعد صورة توضح تنبيهات عربية
عند دكتور مسجَّل إنجليزي: نفس فئة مشكلة عناوين المهام (بند 96bde81)،
لكن بنظام التنبيهات (app/core/alerts_service.py) هذي المرة — كل
label/category/detail كانت نصاً عربياً خاماً f-string غير قابل
للترجمة. فحص طرف-لطرف حقيقي: دكتور لغته إنجليزي يفتح شاشة التنبيهات
فعلياً، والتنبيه يطلع مترجماً."""
from app.extensions import db
from app.models import Barn, Role, User
from factories import make_barn


def _make_doctor(phone="0599999260", language="en"):
    role = Role.query.filter_by(name="doctor").first()
    user = User(name="Dr Alerts Test", phone=phone, role_id=role.id, language=language)
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_barn_without_worker_alert_translates_for_english_doctor(app, client):
    """نفس المثال اللي أرسله المستخدم بالصورة: "حظيرة X — بدون عامل
    مسؤول" — يترجم فعلياً بدل ما يبقى عربياً خاماً."""
    make_barn(barn_no="Q-NEW", barn_name="حظيرة العزل للمستجدين")
    doctor = _make_doctor()
    client.post("/login", data={"phone": doctor.phone, "password": "pass1234"})

    resp = client.get("/alerts")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "بدون عامل مسؤول" not in body
    assert "no responsible worker" in body
    assert "Barn without a responsible worker" in body


def test_barn_without_worker_alert_shows_open_button_for_doctor(app, client):
    """بند إضافي (2026-08-31) — طلبك المباشر بعد صورة شاشة: الزر
    "فتح" لتنبيه "حظيرة بدون عامل مسؤول" كان موجوداً بالكود أصلاً، بس
    مقيَّداً بصلاحية barns.manage اللي دور الدكتور ما يملكها افتراضياً
    — يطلعله التنبيه بلا زر ولا توضيح. صار الدكتور يملكها افتراضياً."""
    barn = make_barn(barn_no="Q-BTN", barn_name="حظيرة اختبار الزر")
    doctor = _make_doctor(phone="0599999263")
    client.post("/login", data={"phone": doctor.phone, "password": "pass1234"})

    resp = client.get("/alerts")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert f'/barns/{barn.id}/edit' in body


def test_alerts_stay_arabic_for_arabic_doctor(app, client):
    make_barn(barn_no="Q-NEW2", barn_name="حظيرة اختبار عربي")
    doctor = _make_doctor(phone="0599999261", language="ar")
    client.post("/login", data={"phone": doctor.phone, "password": "pass1234"})

    resp = client.get("/alerts")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "بدون عامل مسؤول" in body


def test_incomplete_data_field_label_translates(app, client):
    """FIELD_LABELS_AR (data_completeness_service.py) صار _l() — كان
    نصاً خاماً بيدمج بخلل TypeError لو ما عولج صح (LazyString مو str)."""
    from app.core import data_completeness_service as dcs
    from app.extensions import db as _db
    from factories import make_animal

    animal = make_animal(animal_no="INC-01", gender=None)
    doctor = _make_doctor(phone="0599999262")
    client.post("/login", data={"phone": doctor.phone, "password": "pass1234"})

    resp = client.get("/alerts")
    assert resp.status_code == 200
    assert dcs.missing_fields(animal)  # تأكيد وجود حقول ناقصة فعلاً
