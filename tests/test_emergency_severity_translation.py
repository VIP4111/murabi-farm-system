"""فجوة إضافية (بحث فجوات 2026-08-31): شاشة "قائمة أعراض الطوارئ"
(إعداد للدكتور/صاحب الحلال) كانت تعرض درجة الخطورة ("حرجة"/"شديدة")
كنص عربي خام دائماً بغض النظر عن لغة الحساب — نفس القيمة المخزَّنة
تُستخدم أيضاً للمقارنة المنطقية (تلوين الشارة)، فالإصلاح يترجم العرض
فقط ويبقي القيمة المخزَّنة/المقارَن بها كما هي."""
from app.extensions import db
from app.models import Role, User


def test_emergency_symptoms_severity_translates_for_english_user(app, client):
    from app.models.health import EmergencySymptom, Symptom

    symptom = Symptom.query.first() or Symptom(name="عرض اختبار", is_primary=True)
    if not symptom.id:
        db.session.add(symptom)
        db.session.commit()
    entry = EmergencySymptom(symptom_id=symptom.id, severity="حرجة", differential="-", advice="-")
    db.session.add(entry)

    role = Role.query.filter_by(name="doctor").first()
    doctor = User(name="Dr EN Severity", phone="0599999352", role_id=role.id, language="en")
    doctor.set_password("pass1234")
    db.session.add(doctor)
    db.session.commit()

    client.post("/login", data={"phone": doctor.phone, "password": "pass1234"})
    resp = client.get("/health/emergency-symptoms")
    body = resp.data.decode()
    assert ">حرجة<" not in body
    assert "Critical" in body
