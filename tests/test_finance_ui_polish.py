"""بند إضافي 124 — تبسيط شاشة المالية للمحاسب/المشاهد: أرقام إجمالية
بتنسيق KPI موحّد (.stat)، جدول ملفوف بغلاف تمرير أفقي للجوال
(.table-scroll)، وفورم العملية الجديدة يخفي الحقول غير المرتبطة
بالنوع المختار."""
from app.extensions import db
from app.models import Role, User


def _make_doctor():
    role = Role.query.filter_by(name="doctor").first()
    user = User(name="دكتور اختبار الواجهة", phone="0599999125", role_id=role.id, language="ar")
    user.set_password("test1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_finance_list_uses_stat_cards_and_table_scroll_wrapper(app, client):
    role = Role.query.filter_by(name="owner").first()
    owner = User(name="مالك اختبار المالية", phone="0599999126", role_id=role.id, language="ar")
    owner.set_password("test1234")
    db.session.add(owner)
    db.session.commit()

    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    resp = client.get("/finance/")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert 'class="stat"' in body
    assert 'class="table-scroll"' in body
    assert 'btn danger' in body or 'class="btn' in body


def test_finance_health_view_uses_stat_and_table_scroll(app, client):
    doctor = _make_doctor()
    client.post("/login", data={"phone": doctor.phone, "password": "test1234"})
    resp = client.get("/finance/health")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert 'class="stat"' in body
    assert 'class="table-scroll"' in body


def test_finance_new_form_has_conditional_field_groups(app, client):
    role = Role.query.filter_by(name="owner").first()
    owner = User(name="مالك اختبار فورم المالية", phone="0599999127", role_id=role.id, language="ar")
    owner.set_password("test1234")
    db.session.add(owner)
    db.session.commit()

    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    resp = client.get("/finance/new")
    body = resp.data.decode()
    assert 'id="debtInHint"' in body
    assert 'id="indirectExpenseGroup"' in body
    assert "operationTypeSelect" in body
