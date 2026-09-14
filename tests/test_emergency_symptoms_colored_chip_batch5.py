"""اختبار بند التصميم "بلاطات مراح" (طلبك: "استمر حتى تغطي كل
الشاشات") — دفعة خامسة (الأخيرة بعد الفحص الشامل): قائمة أعراض
الطوارئ."""
from app.extensions import db
from app.models.health import EmergencySymptom
from tests.factories import make_symptom


def test_emergency_symptoms_list_shows_severity_chip(logged_in_client):
    s = make_symptom(name="عرض طوارئ اختبار")
    entry = EmergencySymptom(symptom_id=s.id, severity="حرجة", differential="تشخيص اختبار", advice="توصية اختبار")
    db.session.add(entry)
    db.session.commit()

    resp = logged_in_client.get("/health/emergency-symptoms")
    assert resp.status_code == 200
    assert b"emergency-severity-chip" in resp.data
