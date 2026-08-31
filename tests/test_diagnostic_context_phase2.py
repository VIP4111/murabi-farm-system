"""بند إضافي 127، المرحلة 2 — حرارة رقمية + عمر الرأس كسياق عرض
بشاشة المساعد التشخيصي. عرض توجيهي بس بهذي المرحلة، بدون أي تأثير
على score_diagnoses (مؤجَّل للمرحلة 3 حسب الخطة المتفَق عليها)."""
from datetime import date, timedelta
from app.extensions import db
from app.health import health_service
from app.models import Role, User
from factories import make_animal, make_symptom, make_disease_type, link_symptom


def _make_doctor(phone="0599999144"):
    role = Role.query.filter_by(name="doctor").first()
    user = User(name="دكتور اختبار الحرارة", phone=phone, role_id=role.id, language="ar")
    user.set_password("test1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_classify_temperature_ranges():
    # بند إضافي (2026-08-31) — classify_temperature() صارت ترجّع رمزاً
    # داخلياً ثابتاً (low/high/normal) بدل نص عربي مباشر، عشان تسميته
    # المعروضة تُترجم فعلياً لحساب غير عربي (temperature_label()).
    assert health_service.classify_temperature(None) is None
    assert health_service.classify_temperature(37.5) == "low"
    assert health_service.classify_temperature(39.0) == "normal"
    assert health_service.classify_temperature(41.0) == "high"


def test_animal_age_label_from_birth_date(app):
    animal = make_animal(animal_no="AGE-01")
    animal.birth_date = date.today() - timedelta(days=45)
    db.session.commit()
    assert health_service.animal_age_label(animal) == "45 يوم"


def test_animal_age_label_none_without_birth_date(app):
    animal = make_animal(animal_no="AGE-02")
    assert health_service.animal_age_label(animal) is None


def test_diagnose_result_displays_temperature_and_age(app, client):
    doctor = _make_doctor()
    fever = make_symptom("حرارة اختبار المرحلة 2", is_primary=True)
    disease = make_disease_type("مرض اختبار المرحلة 2")
    link_symptom(disease, fever, weight=2)
    animal = make_animal(animal_no="AGE-03")
    animal.birth_date = date.today() - timedelta(days=400)
    db.session.commit()

    client.post("/login", data={"phone": doctor.phone, "password": "test1234"})
    resp = client.post("/health/diagnose/result", data={
        "animal_id": str(animal.id), "temperature": "41.2", "symptom_ids": str(fever.id),
    })
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "41.2" in body
    assert "مرتفعة عن الطبيعي" in body
    assert "13 شهر" in body


def test_diagnose_start_get_carries_temperature_in_hidden_field(app, client):
    doctor = _make_doctor(phone="0599999145")
    fever = make_symptom("حرارة اختبار المرحلة 2 ب", is_primary=True)
    client.post("/login", data={"phone": doctor.phone, "password": "test1234"})
    resp = client.get(f"/health/diagnose?primary={fever.id}&temperature=39.8")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert 'name="temperature" value="39.8"' in body
