"""بند إصلاح (فحص عميق — طلبك: "ابدأ فحص عميق لباقي الشاشات") — عنوان
شاشة "إضافة نوع بلاغ جديد" كان النداء الوحيد لـ`animal_option_form.html`
اللي ما يغلّف `title` بـ`_()` (كل نظائرها — فصيلة/سلالة/لون/طريقة
استخدام — تفعل ذلك)."""
from app.extensions import db
from app.models import Role, User
from flask_babel import force_locale


def test_report_types_new_screen_title_translates_to_english(app, client):
    role = Role.query.filter_by(name="owner").first()
    owner = User(name="EO", phone="0500099901", role_id=role.id, language="en")
    owner.set_password("pass1234")
    db.session.add(owner)
    db.session.commit()
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    resp = client.get("/team/reports/types/new")
    assert resp.status_code == 200
    assert "إضافة نوع بلاغ جديد".encode() not in resp.data
