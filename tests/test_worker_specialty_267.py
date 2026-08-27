"""بند إضافي 267 — طلبك الصريح: "عندي عمالة مسؤولة عن الزراعة/الأعلاف
بالمزرعة، بالتقارير المسمى الوظيفي عامل لهم كلهم". أضفنا حقل تخصص/
مسمى وظيفي إضافي اختياري — **منفصل تماماً عن الدور (Role)**: الدور
يبقى "عامل" بنفس الصلاحيات لكل عمّالك، التخصص وصف إضافي للعرض بس."""
from app.extensions import db
from app.models import User


def test_members_new_saves_specialty(app, logged_in_client):
    from app.models import Role
    role = Role.query.filter_by(name="worker").first()
    resp = logged_in_client.post("/team/members/new", data={
        "name": "عامل زراعي", "phone": "0500067001", "password": "pass1234",
        "role_id": str(role.id), "language": "ar", "specialty": "زراعة أعلاف",
    }, follow_redirects=True)
    assert resp.status_code == 200
    worker = User.query.filter_by(phone="0500067001").first()
    assert worker is not None
    assert worker.specialty == "زراعة أعلاف"
    assert worker.role.name == "worker"  # الدور بقي "عامل" زي أي عامل ثاني


def test_members_edit_updates_specialty(app, logged_in_client, worker):
    resp = logged_in_client.post(f"/team/members/{worker.id}/edit", data={
        "name": worker.name, "phone": worker.phone, "role_id": str(worker.role_id),
        "language": "ar", "specialty": "سائق",
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(worker)
    assert worker.specialty == "سائق"


def test_members_edit_clears_specialty_when_emptied(app, logged_in_client, worker):
    worker.specialty = "زراعة أعلاف"
    db.session.commit()
    logged_in_client.post(f"/team/members/{worker.id}/edit", data={
        "name": worker.name, "phone": worker.phone, "role_id": str(worker.role_id),
        "language": "ar", "specialty": "",
    }, follow_redirects=True)
    db.session.refresh(worker)
    assert worker.specialty is None


def test_members_list_shows_specialty_alongside_role_not_instead_of_it(app, logged_in_client, worker):
    worker.specialty = "زراعة أعلاف"
    db.session.commit()
    resp = logged_in_client.get("/team/members")
    html = resp.data.decode()
    assert "زراعة أعلاف" in html
    assert worker.role.display_name in html  # "العامل" لسا موجود، ما انبدل


def test_members_list_without_specialty_shows_role_only(app, logged_in_client, worker):
    resp = logged_in_client.get("/team/members")
    html = resp.data.decode()
    assert worker.role.display_name in html
