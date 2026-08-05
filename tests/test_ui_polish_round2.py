"""بند إضافي 126 — استمرار تحسين UI/UX: شاشة برنامج التزامن التناسلي
(repro)، تفاصيل البلاغ، وجداول التقارير التحليلية الخمسة — كلها صارت
تستخدم `.table-scroll` (تمرير أفقي على الجوال بدل تمديد الصفحة)
وشارات حالة موحّدة بدل badge on/off اليدوي."""
from datetime import date
from app.extensions import db
from app.models import Role, User, Barn, Animal
from app.models.repro import TwinEstrusProgram
from factories import make_animal


def _make_owner(phone="0599999129"):
    role = Role.query.filter_by(name="owner").first()
    user = User(name="مالك اختبار الواجهة 2", phone=phone, role_id=role.id, language="ar")
    user.set_password("test1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_program_detail_uses_table_scroll_and_status_badge(app, client):
    owner = _make_owner()
    ewe = make_animal(animal_no="PRG-01", gender="أنثى")
    program = TwinEstrusProgram(ewe_id=ewe.id, status="active", start_date=date.today())
    db.session.add(program)
    db.session.commit()

    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    resp = client.get(f"/repro/programs/{program.id}")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert 'class="table-scroll"' in body
    assert 'data-state=' in body


def test_report_detail_uses_danger_class_not_inline_style(app, client):
    from app.team import report_service as svc
    owner = _make_owner(phone="0599999130")
    animal = make_animal(animal_no="RPT-01")
    report = svc.submit_report(reporter=owner, description="اختبار", animal_id=animal.id)

    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    resp = client.get(f"/team/reports/{report.id}")
    body = resp.data.decode()
    assert "background:#a32d2d" not in body
    assert 'class="btn danger"' in body


def test_report_screens_use_table_scroll(app, client):
    owner = _make_owner(phone="0599999131")
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    for path in ("/reports/mortality", "/reports/births", "/reports/sales", "/reports/activity", "/reports/purchase_request"):
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert 'class="table-scroll"' in resp.data.decode(), path
