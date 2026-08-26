"""بند إضافي 241 — نقطة بداية نظام الرواتب الشهري العام: راتب أساسي
ثابت لكل عضو فريق، يعدّله صاحب الحلال أو المحاسب (صلاحية
team.manage_salary منفصلة عن users.manage الكاملة، بطلبك الصريح)."""
from app.extensions import db
from app.models import Role, User


def _accountant(client):
    role = Role.query.filter_by(name="accountant").first()
    u = User(name="محاسب اختبار", phone="0500033001", role_id=role.id, language="ar")
    u.set_password("pass1234")
    db.session.add(u)
    db.session.commit()
    client.post("/login", data={"phone": u.phone, "password": "pass1234"})
    return u


def _worker():
    role = Role.query.filter_by(name="worker").first()
    u = User(name="عامل اختبار", phone="0500033002", role_id=role.id, language="ar")
    u.set_password("pass1234")
    db.session.add(u)
    db.session.commit()
    return u


def test_accountant_role_has_salary_permission_by_default(app):
    accountant_role = Role.query.filter_by(name="accountant").first()
    codes = {p.code for p in accountant_role.permissions}
    assert "team.manage_salary" in codes
    assert "users.manage" not in codes


def test_accountant_can_view_salaries_list(app, client):
    _accountant(client)
    resp = client.get("/team/salaries")
    assert resp.status_code == 200


def test_accountant_cannot_view_full_members_list(app, client):
    _accountant(client)
    resp = client.get("/team/members")
    assert resp.status_code == 403


def test_worker_forbidden_from_salaries_list(app, client):
    worker = _worker()
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.get("/team/salaries")
    assert resp.status_code == 403


def test_accountant_can_update_salary(app, client):
    _accountant(client)
    worker = _worker()
    resp = client.post(f"/team/salaries/{worker.id}/update", data={"base_salary": "2500"},
                        follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(worker)
    assert worker.base_salary == 2500.0


def test_clearing_salary_sets_none(app, client):
    _accountant(client)
    worker = _worker()
    worker.base_salary = 1000
    db.session.commit()
    client.post(f"/team/salaries/{worker.id}/update", data={"base_salary": ""})
    db.session.refresh(worker)
    assert worker.base_salary is None


def test_owner_also_has_salary_permission(app, logged_in_client, owner):
    resp = logged_in_client.get("/team/salaries")
    assert resp.status_code == 200
