"""فحص عميق — شاشة الأدوار والصلاحيات: `members_new`/`members_edit`
كانتا تسمحان لأي حساب عنده صلاحية `users.manage` (أخف كثيراً من "صاحب
الحلال" — يمكن تُمنح لدور مخصَّص زي "موارد بشرية") بترقية أي حساب
لدور "owner" مباشرة، أو بتغيير دور صاحب الحلال الفعلي بعيداً عنه —
تصعيد صلاحيات كامل (أو تعطيل وصول المالك) بضغطة وحدة بدون أي عائق."""
from app.extensions import db
from app.models import User, Role, Permission


def _make_hr_manager_with_users_manage():
    """دور مخصَّص عنده `users.manage` بس — مو owner، ونفس الحد الأدنى
    الواقعي اللي قد يُمنح لدور "موارد بشرية" بمزرعة حقيقية."""
    role = Role(name="hr_manager", display_name="موارد بشرية", is_system=False)
    perm = Permission.query.filter_by(code="users.manage").first()
    role.permissions = [perm]
    db.session.add(role)
    db.session.flush()
    user = User(name="موظف موارد بشرية", phone="0500009001", role_id=role.id, language="ar")
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_non_owner_cannot_create_member_with_owner_role(app, client, owner):
    hr_user = _make_hr_manager_with_users_manage()
    owner_role = Role.query.filter_by(name="owner").first()
    client.post("/login", data={"phone": hr_user.phone, "password": "pass1234"})

    resp = client.post("/team/members/new", data={
        "name": "متسلل", "phone": "0500009002", "password": "pass1234",
        "role_id": str(owner_role.id), "language": "ar",
    }, follow_redirects=True)
    assert resp.status_code == 200

    created = User.query.filter_by(phone="0500009002").first()
    assert created is None, "انشأ حساباً بدور صاحب الحلال رغم إنه مو owner — تصعيد صلاحيات"


def test_non_owner_cannot_promote_existing_member_to_owner_role(app, client, owner, worker):
    hr_user = _make_hr_manager_with_users_manage()
    owner_role = Role.query.filter_by(name="owner").first()
    worker_original_role_id = worker.role_id
    client.post("/login", data={"phone": hr_user.phone, "password": "pass1234"})

    resp = client.post(f"/team/members/{worker.id}/edit", data={
        "name": worker.name, "phone": worker.phone, "role_id": str(owner_role.id), "language": "ar",
    }, follow_redirects=True)
    assert resp.status_code == 200

    db.session.refresh(worker)
    assert worker.role_id == worker_original_role_id, "عامل انترقّى لدور صاحب الحلال رغم إن المعدِّل مو owner"


def test_non_owner_cannot_demote_the_actual_owner_account(app, client, owner, worker):
    hr_user = _make_hr_manager_with_users_manage()
    worker_role_id = worker.role_id
    owner_original_role_id = owner.role_id
    client.post("/login", data={"phone": hr_user.phone, "password": "pass1234"})

    resp = client.post(f"/team/members/{owner.id}/edit", data={
        "name": owner.name, "phone": owner.phone, "role_id": str(worker_role_id), "language": "ar",
    }, follow_redirects=True)
    assert resp.status_code == 200

    db.session.refresh(owner)
    assert owner.role_id == owner_original_role_id, "دور صاحب الحلال الفعلي تغيّر رغم إن المعدِّل مو owner"


def test_owner_can_still_promote_a_member_to_owner_role(app, logged_in_client, worker):
    """التأكد إن الإصلاح ما كسر القدرة الشرعية: owner نفسه لسا يقدر
    يرقّي حساباً ثانياً لدور صاحب الحلال (تسليم الإدارة، مثلاً)."""
    owner_role = Role.query.filter_by(name="owner").first()
    resp = logged_in_client.post(f"/team/members/{worker.id}/edit", data={
        "name": worker.name, "phone": worker.phone, "role_id": str(owner_role.id), "language": "ar",
    }, follow_redirects=True)
    assert resp.status_code == 200

    db.session.refresh(worker)
    assert worker.role_id == owner_role.id
