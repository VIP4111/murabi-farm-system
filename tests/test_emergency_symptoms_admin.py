"""بند إضافي 127، المرحلة 4 (الأخيرة) — قائمة أعراض الطوارئ صارت
جدولاً ديناميكياً (`EmergencySymptom`) بدل قاموس ثابت بالكود، بلوحة
إدارة كاملة (إضافة/حذف) وseed idempotent لأول 3 أعراض معتمَدة."""
from app.extensions import db
from app.models import Role, User, Symptom, EmergencySymptom
from factories import make_symptom


def _make_doctor(phone="0599999149"):
    role = Role.query.filter_by(name="doctor").first()
    user = User(name="دكتور اختبار قائمة الطوارئ", phone=phone, role_id=role.id, language="ar")
    user.set_password("test1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_emergency_symptoms_list_renders(app, client):
    doctor = _make_doctor()
    client.post("/login", data={"phone": doctor.phone, "password": "test1234"})
    resp = client.get("/health/emergency-symptoms")
    assert resp.status_code == 200
    assert "قائمة أعراض الطوارئ" in resp.data.decode()


def test_emergency_symptoms_new_creates_entry(app, client):
    doctor = _make_doctor(phone="0599999150")
    symptom = make_symptom("عرض طوارئ اختبار الإضافة")
    client.post("/login", data={"phone": doctor.phone, "password": "test1234"})

    resp = client.post("/health/emergency-symptoms/new", data={
        "symptom_id": str(symptom.id), "severity": "حرجة",
        "differential": "اشتباه اختباري", "advice": "توصية اختبارية",
    })
    assert resp.status_code == 302
    entry = EmergencySymptom.query.filter_by(symptom_id=symptom.id).first()
    assert entry is not None
    assert entry.severity == "حرجة"


def test_emergency_symptoms_new_rejects_duplicate_symptom(app, client):
    doctor = _make_doctor(phone="0599999151")
    symptom = make_symptom("عرض طوارئ اختبار التكرار")
    db.session.add(EmergencySymptom(symptom_id=symptom.id, severity="شديدة",
                                     differential="س", advice="ص"))
    db.session.commit()
    client.post("/login", data={"phone": doctor.phone, "password": "test1234"})

    resp = client.post("/health/emergency-symptoms/new", data={
        "symptom_id": str(symptom.id), "severity": "حرجة",
        "differential": "تكرار", "advice": "تكرار",
    }, follow_redirects=True)
    assert "مسجَّل بقائمة الطوارئ أصلاً" in resp.data.decode()
    assert EmergencySymptom.query.filter_by(symptom_id=symptom.id).count() == 1


def test_emergency_symptoms_delete_removes_entry(app, client):
    doctor = _make_doctor(phone="0599999152")
    symptom = make_symptom("عرض طوارئ اختبار الحذف")
    entry = EmergencySymptom(symptom_id=symptom.id, severity="شديدة", differential="س", advice="ص")
    db.session.add(entry)
    db.session.commit()
    client.post("/login", data={"phone": doctor.phone, "password": "test1234"})

    resp = client.post(f"/health/emergency-symptoms/{entry.id}/delete")
    assert resp.status_code == 302
    assert EmergencySymptom.query.get(entry.id) is None


def test_check_emergency_symptoms_queries_db_table(app):
    from app.health import health_service
    from factories import make_animal, make_barn

    make_barn(barn_no="ISO-EM4", barn_type="عزل")
    animal = make_animal(animal_no="EM-DYN-01")
    symptom = make_symptom("عرض طوارئ ديناميكي اختبار")
    db.session.add(EmergencySymptom(symptom_id=symptom.id, severity="حرجة",
                                     differential="اشتباه ديناميكي", advice="توصية ديناميكية"))
    db.session.commit()

    result = health_service.check_emergency_symptoms(
        animal_id=animal.id, symptom_names=[symptom.name], actor_user_id=1,
    )
    assert result is not None
    assert result["differentials"] == ["اشتباه ديناميكي"]
    assert result["severities"] == ["حرجة"]


def test_seed_creates_three_initial_emergency_symptoms(app):
    runner = app.test_cli_runner()
    runner.invoke(args=["seed"])
    names = {e.symptom.name for e in EmergencySymptom.query.all()}
    assert "عمى مفاجئ / عتامة العين" in names
    assert "إسهال مدمى حاد" in names
    assert "إجهاض مفاجئ" in names

    count_after_first = EmergencySymptom.query.count()
    runner.invoke(args=["seed"])
    assert EmergencySymptom.query.count() == count_after_first
