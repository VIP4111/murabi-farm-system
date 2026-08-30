"""بند إضافي (2026-08-30) — طلبك الصريح: "حط لي زر نسخ معلومات تسجيل
الدخول علشان انسخها وارسلها لأعضاء الفريق". نسخ عميل-جانبي بحت من
الحقول مباشرة (بدون أي تخزين إضافي بالخادم) — أسلم مكان ممكن، لأنه
اللحظة الوحيدة اللي كلمة المرور نص صريح فيها أصلاً قبل ما تُشفَّر."""
from app.models import Role, User


def test_new_member_form_includes_copy_button(app, logged_in_client):
    resp = logged_in_client.get("/team/members/new")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert 'id="copyLoginInfoBtn"' in body
    assert 'id="memberPhoneInput"' in body
    assert 'id="memberPasswordInput"' in body
    assert "نسخ بيانات الدخول" in body


def test_edit_member_form_includes_copy_button(app, logged_in_client):
    role = Role.query.filter_by(name="worker").first()
    member = User(name="عضو اختبار النسخ", phone="0599999290", role_id=role.id)
    member.set_password("pass1234")
    from app.extensions import db
    db.session.add(member)
    db.session.commit()

    resp = logged_in_client.get(f"/team/members/{member.id}/edit")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert 'id="copyLoginInfoBtn"' in body
    assert 'id="memberPasswordInput"' in body


def test_worker_without_users_manage_permission_cannot_reach_form(app, client, worker):
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.get("/team/members/new")
    assert resp.status_code == 403
