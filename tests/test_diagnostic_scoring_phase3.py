"""بند إضافي 127، المرحلة 3 — معادلة موزونة: (مجموع أوزان مطابقة ×
معامل سياق) - غرامة عرض إجباري ناقص، استبعاد كامل لو عرض استبعادي
مُدخَل، والنتيجة النهائية % توافق بدل نقاط مبهمة."""
from app.health import health_service
from factories import make_disease_type, make_symptom, link_symptom


def test_full_match_gives_100_percent(app):
    disease = make_disease_type("مرض اختبار 100%")
    s1 = make_symptom("عرض كامل 1")
    s2 = make_symptom("عرض كامل 2")
    link_symptom(disease, s1, weight=3)
    link_symptom(disease, s2, weight=2)

    results = health_service.score_diagnoses(symptom_ids=[s1.id, s2.id])
    assert results[0]["match_percent"] == 100


def test_partial_match_gives_proportional_percent(app):
    disease = make_disease_type("مرض اختبار جزئي")
    s1 = make_symptom("عرض جزئي 1")
    s2 = make_symptom("عرض جزئي 2")
    link_symptom(disease, s1, weight=2)
    link_symptom(disease, s2, weight=2)

    results = health_service.score_diagnoses(symptom_ids=[s1.id])
    assert results[0]["match_percent"] == 50


def test_missing_required_symptom_lowers_percent_and_is_flagged(app):
    disease = make_disease_type("مرض اختبار الإجباري")
    required = make_symptom("عرض إجباري مفقود")
    other = make_symptom("عرض ثانوي مطابق")
    link_symptom(disease, required, weight=3, is_required=True)
    link_symptom(disease, other, weight=2)

    results = health_service.score_diagnoses(symptom_ids=[other.id])
    assert len(results) == 1
    # raw=2, penalty=3 -> max(0, 2-3)=0 -> 0%
    assert results[0]["match_percent"] == 0
    assert "عرض إجباري مفقود" in results[0]["missing_required_symptoms"]


def test_exclusionary_symptom_removes_disease_entirely(app):
    disease = make_disease_type("مرض اختبار الاستبعاد")
    exclusionary = make_symptom("عرض يستبعد")
    other = make_symptom("عرض مصاحب استبعاد")
    link_symptom(disease, exclusionary, weight=1, is_exclusionary=True)
    link_symptom(disease, other, weight=3)

    results = health_service.score_diagnoses(symptom_ids=[exclusionary.id, other.id])
    assert results == []


def test_fever_context_boosts_score_and_flags_context_boosted(app):
    disease = make_disease_type("مرض اختبار الحمى")
    s1 = make_symptom("عرض حمى 1")
    s2 = make_symptom("عرض حمى 2")
    s3 = make_symptom("عرض حمى 3")
    link_symptom(disease, s1, weight=2)
    link_symptom(disease, s2, weight=2)
    link_symptom(disease, s3, weight=2)

    without_fever = health_service.score_diagnoses(symptom_ids=[s1.id])
    with_fever = health_service.score_diagnoses(symptom_ids=[s1.id], temperature=41.0)

    assert with_fever[0]["match_percent"] > without_fever[0]["match_percent"]
    assert with_fever[0]["context_boosted"] is True
    assert without_fever[0]["context_boosted"] is False


def test_normal_temperature_does_not_boost(app):
    disease = make_disease_type("مرض اختبار حرارة طبيعية")
    s1 = make_symptom("عرض حرارة طبيعية")
    link_symptom(disease, s1, weight=2)

    results = health_service.score_diagnoses(symptom_ids=[s1.id], temperature=39.0)
    assert results[0]["context_boosted"] is False


def test_diagnose_result_route_shows_percent_and_required_warning(app, client):
    from app.extensions import db
    from app.models import Role, User

    role = Role.query.filter_by(name="doctor").first()
    doctor = User(name="دكتور اختبار المرحلة 3", phone="0599999147", role_id=role.id, language="ar")
    doctor.set_password("test1234")
    db.session.add(doctor)
    db.session.commit()

    disease = make_disease_type("مرض اختبار شاشة النتيجة")
    required = make_symptom("عرض إجباري بشاشة النتيجة")
    other = make_symptom("عرض ثانوي بشاشة النتيجة")
    link_symptom(disease, required, weight=3, is_required=True)
    link_symptom(disease, other, weight=1)

    client.post("/login", data={"phone": doctor.phone, "password": "test1234"})
    resp = client.post("/health/diagnose/result", data={"symptom_ids": str(other.id)})
    body = resp.data.decode()
    assert "%" in body
    assert "ناقص عرض إجباري" in body
