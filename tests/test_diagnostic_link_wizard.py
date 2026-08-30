"""بند إضافي 127، تكملة — المعالج التفاعلي لربط الأعراض بالأمراض،
وحقل "يتطلب عزل فوري" الجديد. + فحص مكتبة الأمراض الموسّعة (استيراد
idempotent، دمج بأمراض موجودة، وزن مقصوص عند 3)."""
from app.extensions import db
from app.models import Role, User, DiseaseSymptomLink
from factories import make_disease_type, make_symptom


def _make_doctor(phone="0599999140"):
    role = Role.query.filter_by(name="doctor").first()
    user = User(name="دكتور اختبار المعالج", phone=phone, role_id=role.id, language="ar")
    user.set_password("test1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_link_wizard_get_renders(app, client):
    doctor = _make_doctor()
    client.post("/login", data={"phone": doctor.phone, "password": "test1234"})
    resp = client.get("/health/disease-types/link-wizard")
    assert resp.status_code == 200
    assert "معالج ربط عرض بمرض" in resp.data.decode()


def test_link_wizard_post_creates_links_for_multiple_symptoms(app, client):
    doctor = _make_doctor(phone="0599999141")
    disease = make_disease_type("مرض اختبار المعالج")
    s1 = make_symptom("عرض معالج 1")
    s2 = make_symptom("عرض معالج 2")
    client.post("/login", data={"phone": doctor.phone, "password": "test1234"})

    resp = client.post("/health/disease-types/link-wizard", data={
        "disease_id": str(disease.id),
        "symptom_ids": [str(s1.id), str(s2.id)],
        "weight": "3", "is_required": "1", "is_exclusionary": "",
        "requires_isolation": "1",
    })
    assert resp.status_code == 302
    links = DiseaseSymptomLink.query.filter_by(disease_type_id=disease.id).all()
    assert len(links) == 2
    for link in links:
        assert link.weight == 3
        assert link.is_required is True
        assert link.requires_isolation is True


def test_link_wizard_post_without_symptoms_rejected(app, client):
    doctor = _make_doctor(phone="0599999142")
    disease = make_disease_type("مرض اختبار بلا أعراض")
    client.post("/login", data={"phone": doctor.phone, "password": "test1234"})
    resp = client.post("/health/disease-types/link-wizard", data={"disease_id": str(disease.id)},
                        follow_redirects=True)
    assert "لازم تختار عرض واحد على الأقل" in resp.data.decode()


# ---- بند إضافي (2026-08-30) — طلبك: "بحث عن فجوات في الترجمة في حساب
# الدكتور" — رسائل flash بملف health/routes.py كانت نصاً عربياً ثابتاً
# غير مغلَّف بـ_(), فتبقى عربية حتى لو حساب الدكتور إنجليزي.

def test_flash_message_translates_for_english_doctor(app, client):
    """فحص طرف-لطرف حقيقي: دكتور لغته إنجليزي يرسل نفس الطلب الفاشل —
    الرسالة تطلع إنجليزية فعلياً، مو عربية خام."""
    doctor = _make_doctor(phone="0599999143")
    doctor.language = "en"
    db.session.commit()
    disease = make_disease_type("مرض اختبار ترجمة الرسائل")
    client.post("/login", data={"phone": doctor.phone, "password": "test1234"})

    resp = client.post("/health/disease-types/link-wizard", data={"disease_id": str(disease.id)},
                        follow_redirects=True)
    body = resp.data.decode()
    assert "لازم تختار عرض واحد على الأقل" not in body
    assert "You must select at least one symptom" in body


def test_disease_library_v2_seed_is_idempotent_and_clamps_weight(app):
    from app.models import DiseaseType

    runner = app.test_cli_runner()
    runner.invoke(args=["seed"])
    diseases_after_first = DiseaseType.query.count()
    links_after_first = DiseaseSymptomLink.query.count()
    assert diseases_after_first > 12  # 12 الأصلية + مكتبة v2 المدموجة/الجديدة

    max_weight = db.session.query(db.func.max(DiseaseSymptomLink.weight)).scalar()
    assert max_weight is not None and max_weight <= 3

    runner.invoke(args=["seed"])
    assert DiseaseType.query.count() == diseases_after_first
    assert DiseaseSymptomLink.query.count() == links_after_first

    # تأكيد الدمج: "التهاب الضرع" يبقى سجل واحد، مو مكرَّر باسم مختلف
    assert DiseaseType.query.filter_by(name="التهاب الضرع").count() == 1
    mastitis = DiseaseType.query.filter_by(name="التهاب الضرع").first()
    assert mastitis.notes and "دواء مرجعي" in mastitis.notes
