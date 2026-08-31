"""فجوة إضافية اكتُشفت ببحث فجوات (2026-08-31): شاشة نتيجة التشخيص
(`/health/diagnose/result`) كانت تبني تصنيف درجة الحرارة، ونص "مقترح
من المساعد التشخيصي..." المُمرَّر لشاشة تسجيل المرض التالية، كنص عربي
ثابت مباشر — يظهر بالعربي حتى بحساب إنجليزي بالكامل.

الإصلاح: `classify_temperature()` (app/health/health_service.py) صارت
ترجّع رمزاً داخلياً ثابتاً (low/high/normal) بدل نص عربي مباشر، وأضيفت
`temperature_label()` لترجمة الرمز وقت العرض. رابط "استخدم هذا
الاحتمال" صار يبني نص diagnosis_note عبر `_()` مع kwargs.
"""
from app.health import health_service


def test_classify_temperature_returns_stable_code():
    assert health_service.classify_temperature(35.0) == "low"
    assert health_service.classify_temperature(41.0) == "high"
    assert health_service.classify_temperature(39.0) == "normal"
    assert health_service.classify_temperature(None) is None


def test_temperature_label_translates_for_english_locale(app):
    from flask_babel import force_locale

    with force_locale("en"):
        assert health_service.temperature_label("high") == "Above normal (possible fever)"
        assert health_service.temperature_label("low") == "Below normal"
        assert health_service.temperature_label("normal") == "Within normal range"
    with force_locale("ar"):
        assert health_service.temperature_label("high") == "مرتفعة عن الطبيعي (حمى محتملة)"


def test_diagnose_result_page_shows_translated_temperature_note(app, client):
    from app.extensions import db
    from app.models import Role, User

    role = Role.query.filter_by(name="doctor").first()
    doctor = User(name="Dr EN Temp", phone="0599999351", role_id=role.id, language="en")
    doctor.set_password("pass1234")
    db.session.add(doctor)
    db.session.commit()

    client.post("/login", data={"phone": doctor.phone, "password": "pass1234"})
    resp = client.post(
        "/health/diagnose/result",
        data={"symptom_ids": [], "free_text_symptoms": "", "temperature": "41"},
    )
    body = resp.data.decode()
    assert "مرتفعة عن الطبيعي" not in body
    assert "Above normal (possible fever)" in body
