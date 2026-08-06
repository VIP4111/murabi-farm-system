"""بند إضافي 127، المرحلة 1 — لوحة إدارة شجرة التشخيص من الواجهة
(بدل تعديل DISEASE_SYMPTOMS بـapp/cli.py وإعادة نشر). يغطي: إضافة
عرض جديد، ربط عرض بمرض مع حقلي إجباري/استبعادي الجديدين، تعديل رابط
موجود، وحذفه — بدون أي تأثير على محرك score_diagnoses الحالي (مؤجَّل
عمداً للمرحلة 3)."""
from app.extensions import db
from app.models import Role, User, Symptom, DiseaseSymptomLink
from app.health import health_service
from factories import make_disease_type, make_symptom, link_symptom


def _make_doctor(phone="0599999133"):
    role = Role.query.filter_by(name="doctor").first()
    user = User(name="دكتور اختبار شجرة التشخيص", phone=phone, role_id=role.id, language="ar")
    user.set_password("test1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_symptoms_new_creates_symptom(app, client):
    doctor = _make_doctor()
    client.post("/login", data={"phone": doctor.phone, "password": "test1234"})
    resp = client.post("/health/symptoms/new", data={"name": "طرف بارد", "is_primary": "1"})
    assert resp.status_code == 302
    s = Symptom.query.filter_by(name="طرف بارد").first()
    assert s is not None
    assert s.is_primary is True


def test_symptoms_new_rejects_duplicate_name(app, client):
    doctor = _make_doctor(phone="0599999134")
    make_symptom("عرض مكرر")
    client.post("/login", data={"phone": doctor.phone, "password": "test1234"})
    resp = client.post("/health/symptoms/new", data={"name": "عرض مكرر"}, follow_redirects=True)
    assert "موجودة بالقائمة أصلاً" in resp.data.decode() or "موجود بالقائمة أصلاً" in resp.data.decode()
    assert Symptom.query.filter_by(name="عرض مكرر").count() == 1


def test_disease_symptom_link_new_stores_required_and_exclusionary(app, client):
    doctor = _make_doctor(phone="0599999135")
    disease = make_disease_type("مرض اختبار اللوحة")
    symptom = make_symptom("عرض إجباري اختبار")
    client.post("/login", data={"phone": doctor.phone, "password": "test1234"})

    resp = client.post(f"/health/disease-types/{disease.id}/links/new", data={
        "symptom_id": str(symptom.id), "weight": "3", "is_required": "1", "is_exclusionary": "",
    })
    assert resp.status_code == 302
    link = DiseaseSymptomLink.query.filter_by(disease_type_id=disease.id, symptom_id=symptom.id).first()
    assert link is not None
    assert link.weight == 3
    assert link.is_required is True
    assert link.is_exclusionary is False


def test_disease_symptom_link_update_toggles_flags(app, client):
    doctor = _make_doctor(phone="0599999136")
    disease = make_disease_type("مرض اختبار التحديث")
    symptom = make_symptom("عرض اختبار التحديث")
    link = link_symptom(disease, symptom, weight=1)
    client.post("/login", data={"phone": doctor.phone, "password": "test1234"})

    resp = client.post(f"/health/disease-types/links/{link.id}/update", data={
        "weight": "2", "is_exclusionary": "1",
    })
    assert resp.status_code == 302
    db.session.refresh(link)
    assert link.weight == 2
    assert link.is_exclusionary is True
    assert link.is_required is False


def test_disease_symptom_link_delete_removes_row(app, client):
    doctor = _make_doctor(phone="0599999137")
    disease = make_disease_type("مرض اختبار الحذف")
    symptom = make_symptom("عرض اختبار الحذف")
    link = link_symptom(disease, symptom, weight=1)
    client.post("/login", data={"phone": doctor.phone, "password": "test1234"})

    resp = client.post(f"/health/disease-types/links/{link.id}/delete")
    assert resp.status_code == 302
    assert DiseaseSymptomLink.query.get(link.id) is None


def test_required_and_exclusionary_fields_now_affect_scoring_since_phase3(app):
    """بند إضافي 127 المرحلة 3 — التأثير الفعلي لـis_required/
    is_exclusionary صار مفعَّلاً (كان مخزَّناً بس بالمرحلة 1). عرض
    استبعادي مُدخَل يستبعد المرض كلياً من النتائج."""
    disease = make_disease_type("مرض اختبار التأثير الفعلي")
    required_symptom = make_symptom("عرض إجباري لم يُدخَل ٢")
    exclusionary_symptom = make_symptom("عرض استبعادي مُدخَل ٢")
    other_symptom = make_symptom("عرض عادي ٢")
    link_symptom(disease, required_symptom, weight=2, is_required=True)
    link_symptom(disease, exclusionary_symptom, weight=1, is_exclusionary=True)
    link_symptom(disease, other_symptom, weight=2)

    # العرض الاستبعادي مُدخَل -> المرض يُستبعد كلياً من النتائج.
    results = health_service.score_diagnoses(symptom_ids=[exclusionary_symptom.id, other_symptom.id])
    assert results == []


def test_disease_type_detail_page_permission_gated_for_management(app, client):
    """صلاحية health.view تكفي للعرض، بس medical_options.manage لازمة
    للتعديل — فورمات الربط/التعديل/الحذف ما تظهر بدونها."""
    role = Role.query.filter_by(name="nurse").first()
    nurse = User(name="ممرض اختبار الصلاحية", phone="0599999138", role_id=role.id, language="ar")
    nurse.set_password("test1234")
    db.session.add(nurse)
    db.session.commit()
    disease = make_disease_type("مرض اختبار الصلاحية")

    client.post("/login", data={"phone": nurse.phone, "password": "test1234"})
    resp = client.get(f"/health/disease-types/{disease.id}")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "ربط عرض جديد" not in body
