"""اختبارات تعديل بيانات عضو الفريق + تغيير كلمة المرور (بند إضافي 58)."""
from app.extensions import db
from app.models import User


def test_members_edit_get_renders_prefilled_form(app, logged_in_client, worker):
    resp = logged_in_client.get(f"/team/members/{worker.id}/edit")
    assert resp.status_code == 200
    assert worker.phone.encode() in resp.data


def test_members_edit_updates_fields_without_touching_password(app, logged_in_client, worker):
    old_hash = worker.password_hash
    resp = logged_in_client.post(f"/team/members/{worker.id}/edit", data={
        "name": "اسم معدَّل", "phone": worker.phone, "role_id": str(worker.role_id),
        "language": "en",
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(worker)
    assert worker.name == "اسم معدَّل"
    assert worker.language == "en"
    assert worker.password_hash == old_hash


def test_members_edit_changes_password_when_filled(app, logged_in_client, worker):
    resp = logged_in_client.post(f"/team/members/{worker.id}/edit", data={
        "name": worker.name, "phone": worker.phone, "role_id": str(worker.role_id),
        "language": "ar", "new_password": "newpass9",
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(worker)
    assert worker.check_password("newpass9")


def test_members_edit_rejects_duplicate_phone(app, logged_in_client, worker, owner):
    resp = logged_in_client.post(f"/team/members/{worker.id}/edit", data={
        "name": worker.name, "phone": owner.phone, "role_id": str(worker.role_id),
        "language": "ar",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "مستخدم من قبل".encode() in resp.data


def test_members_edit_requires_users_manage_permission(app, client, worker):
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"}, follow_redirects=True)
    resp = client.get(f"/team/members/{worker.id}/edit")
    assert resp.status_code == 403
