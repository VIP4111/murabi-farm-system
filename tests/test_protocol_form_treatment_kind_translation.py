"""بند إصلاح (فحص عميق حي — طلبك: "ابدا فجص باقي الشاشات"، لقيته أثناء
فحص التحجيم بشاشة "بروتوكولات العلاج") — قائمة "نوع الإجراء" (زيارة
بيطرية/حالة مرضية/تطعيم) بفورم إضافة بروتوكول جديد كانت عربي بحت
بغض النظر عن لغة المستخدم — القيم الخام المخزَّنة بـ`treatment_kind`
(vet_visit/disease/vaccination) ما تغيّرت، فقط التسمية المعروضة."""
from app.extensions import db
from app.models import Role, User


def _english_owner():
    role = Role.query.filter_by(name="owner").first()
    u = User(name="EO", phone="0500099944", role_id=role.id, language="en")
    u.set_password("pass1234")
    db.session.add(u)
    db.session.commit()
    return u


def test_protocol_new_form_treatment_kind_options_translate_to_english(app, client):
    owner = _english_owner()
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    resp = client.get("/health/protocols/new")
    assert resp.status_code == 200
    assert "زيارة بيطرية".encode() not in resp.data
    assert "حالة مرضية".encode() not in resp.data
    assert "تطعيم".encode() not in resp.data
    # القيم الخام (option value) تبقى كودات إنجليزية ثابتة مهما كانت اللغة
    assert b'value="vet_visit"' in resp.data
    assert b'value="disease"' in resp.data
    assert b'value="vaccination"' in resp.data
