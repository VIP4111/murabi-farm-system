"""بلّغ المستخدم بصورتَي شاشة حقيقيتين (حساب دكتور إنجليزي، "UMER ABDU
- Dr"): شاشة "Common diseases (suggestions list)" وشاشة تفاصيل مرض
كانتا تعرضان اسم المرض الخام (t.name) بدل t.display_label() —
DiseaseType.name_en/display_label() كانا موجودَين بالكود من قبل
(بند سابق) لكن ما طُبِّقا بكل مكان يعرض اسم المرض. 4 مواقع صُلحت:
disease_types_list.html، disease_type_detail.html، disease_link_wizard.html،
protocols_list.html، diagnose_result.html (نتيجة التشخيص)."""
from app.extensions import db
from app.models import Role, User


def _make_doctor_en(phone):
    role = Role.query.filter_by(name="doctor").first()
    user = User(name="Dr EN Disease Label", phone=phone, role_id=role.id, language="en")
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_disease_types_list_shows_english_name_when_set(app, client):
    from app.models.health import DiseaseType

    disease = DiseaseType(name="الإسهال المدمى", name_en="Bloody diarrhea", notes="-")
    db.session.add(disease)
    db.session.commit()

    doctor = _make_doctor_en("0599999270")
    client.post("/login", data={"phone": doctor.phone, "password": "pass1234"})

    resp = client.get("/health/disease-types")
    body = resp.data.decode()
    assert "Bloody diarrhea" in body
    assert "الإسهال المدمى" not in body


def test_disease_type_detail_title_translates(app, client):
    from app.models.health import DiseaseType

    disease = DiseaseType(name="التهاب الضرع", name_en="Mastitis")
    db.session.add(disease)
    db.session.commit()

    doctor = _make_doctor_en("0599999271")
    client.post("/login", data={"phone": doctor.phone, "password": "pass1234"})

    resp = client.get(f"/health/disease-types/{disease.id}")
    body = resp.data.decode()
    assert "Mastitis" in body
    assert "التهاب الضرع" not in body


def test_disease_type_display_label_falls_back_to_arabic_when_no_english_name(app):
    from app.models.health import DiseaseType

    disease = DiseaseType(name="مرض بلا اسم إنجليزي")
    db.session.add(disease)
    db.session.commit()
    assert disease.display_label() == "مرض بلا اسم إنجليزي"
