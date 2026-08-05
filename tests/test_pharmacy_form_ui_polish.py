"""بند إضافي 125 — تقسيم فورم الصيدلية (أطول فورم بالنظام، 218 سطر
قبل هذا البند) لمجموعات بصرية واضحة بدل تدفّق مسطّح طويل، عبر كلاس
`.form-section-title` عام جديد بـbase.html."""
from app.extensions import db
from app.models import Role, User


def test_pharmacy_new_form_has_section_headers(app, client):
    role = Role.query.filter_by(name="doctor").first()
    doctor = User(name="دكتور اختبار الفورم", phone="0599999128", role_id=role.id, language="ar")
    doctor.set_password("test1234")
    db.session.add(doctor)
    db.session.commit()

    client.post("/login", data={"phone": doctor.phone, "password": "test1234"})
    resp = client.get("/health/pharmacy/new")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert body.count('class="form-section-title"') == 4
    assert "بيانات الدواء الأساسية" in body
    assert "الصلاحية والتخزين" in body
    assert "المخزون والسعر" in body
    assert "أمان إضافي وملاحظات" in body
