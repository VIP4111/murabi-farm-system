"""بند إصلاح (طلبك الصريح، صورة حية: دكتور حسابه إنجليزي شاف قائمة
الأعراض بالمساعد التشخيصي التفاعلي عربي بحت رغم إن باقي الواجهة
إنجليزي) — `Symptom.name_en` + `display_label()` جديدة، نفس نمط
`DiseaseType` الموجود أصلاً بهذا الملف بالضبط."""
from datetime import date

from app.extensions import db
from app.models import Symptom, DiseaseSymptomLink, DiseaseType, Role, User
from app.health import health_service
from tests.factories import make_animal
from flask_babel import force_locale


def test_display_label_returns_english_when_locale_not_arabic(app):
    s = Symptom(name="حرارة", name_en="Fever", is_primary=True)
    db.session.add(s)
    db.session.commit()
    with force_locale("en"):
        assert s.display_label() == "Fever"


def test_display_label_falls_back_to_arabic_when_no_english(app):
    s = Symptom(name="عرض بدون ترجمة", is_primary=True)
    db.session.add(s)
    db.session.commit()
    with force_locale("en"):
        assert s.display_label() == "عرض بدون ترجمة"


def test_display_label_stays_arabic_for_arabic_locale_even_with_english(app):
    s = Symptom(name="حرارة", name_en="Fever", is_primary=True)
    db.session.add(s)
    db.session.commit()
    with force_locale("ar"):
        assert s.display_label() == "حرارة"


def test_diagnose_start_screen_shows_english_symptom_names_for_english_doctor(app, client):
    role = Role.query.filter_by(name="doctor").first()
    doctor = User(name="English Doctor", phone="0500099301", role_id=role.id, language="en")
    doctor.set_password("pass1234")
    db.session.add(doctor)
    db.session.add(Symptom(name="حرارة", name_en="Fever", is_primary=True))
    db.session.commit()

    client.post("/login", data={"phone": doctor.phone, "password": "pass1234"})
    resp = client.get("/health/diagnose")
    assert resp.status_code == 200
    assert b"Fever" in resp.data
    assert "حرارة".encode() not in resp.data


def test_diagnose_result_screen_shows_matched_symptoms_translated(app, client):
    role = Role.query.filter_by(name="doctor").first()
    doctor = User(name="English Doctor", phone="0500099302", role_id=role.id, language="en")
    doctor.set_password("pass1234")
    db.session.add(doctor)

    fever = Symptom(name="حرارة", name_en="Fever", is_primary=True)
    disease = DiseaseType(name="مرض اختبار")
    db.session.add_all([fever, disease])
    db.session.commit()
    db.session.add(DiseaseSymptomLink(disease_type_id=disease.id, symptom_id=fever.id, weight=3))
    db.session.commit()

    client.post("/login", data={"phone": doctor.phone, "password": "pass1234"})
    resp = client.post("/health/diagnose/result", data={"symptom_ids": [str(fever.id)]},
                        follow_redirects=True)
    assert resp.status_code == 200
    assert b"Fever" in resp.data
