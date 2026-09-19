"""فحص شامل سطر بسطر — شاشة أعضاء الفريق: حماية دور المالك ناقصة
بمسارين، وN+1 على عمود الدور بقائمة الأعضاء.

خللان أمنيان حقيقيان اكتُشفا: `members_edit`/`members_new` كانا
محميّين ضد ترقية/تنزيل دور المالك، لكن `members_toggle` (تعطيل/تفعيل
الحساب) و`salary_update` (الراتب وبيانات الهوية) ما فيهما نفس الحماية
— حامل صلاحية أخف (users.manage أو team.manage_salary فقط) يقدر يعطّل
حساب المالك نفسه أو يغيّر راتبه/بيانات هويته."""
from contextlib import contextmanager

from sqlalchemy import event

from app.extensions import db
from app.models import Permission, Role, User


@contextmanager
def count_queries():
    counter = {"n": 0}

    def _on_execute(conn, cursor, statement, parameters, context, executemany):
        counter["n"] += 1

    engine = db.session.get_bind()
    event.listen(engine, "before_cursor_execute", _on_execute)
    try:
        yield counter
    finally:
        event.remove(engine, "before_cursor_execute", _on_execute)


def _make_role_with_permission(role_name, permission_code):
    role = Role(name=role_name, display_name=role_name)
    role.permissions = Permission.query.filter(Permission.code == permission_code).all()
    db.session.add(role)
    db.session.commit()
    return role


def _make_user(name, phone, role_id):
    user = User(name=name, phone=phone, role_id=role_id, language="ar", is_active_account=True)
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_hr_cannot_disable_the_owner_account(app, owner):
    hr_role = _make_role_with_permission("موارد بشرية", "users.manage")
    hr_user = _make_user("موظف موارد بشرية", "0599999600", hr_role.id)

    client = app.test_client()
    client.post("/login", data={"phone": hr_user.phone, "password": "pass1234"})
    resp = client.post(f"/team/members/{owner.id}/toggle", follow_redirects=True)

    db.session.refresh(owner)
    assert owner.is_active_account is True, "ما يصير حامل users.manage يعطّل حساب المالك"
    assert resp.status_code == 200


def test_accountant_cannot_change_owner_salary(app, owner):
    accountant_role = _make_role_with_permission("محاسب", "team.manage_salary")
    accountant = _make_user("محاسب", "0599999601", accountant_role.id)
    original_salary = owner.base_salary

    client = app.test_client()
    client.post("/login", data={"phone": accountant.phone, "password": "pass1234"})
    resp = client.post(f"/team/salaries/{owner.id}/update", data={"base_salary": "99999"},
                        follow_redirects=True)

    db.session.refresh(owner)
    assert owner.base_salary == original_salary, "ما يصير حامل team.manage_salary يغيّر راتب المالك"
    assert resp.status_code == 200


def test_owner_can_still_disable_other_accounts(app, owner):
    hr_role = _make_role_with_permission("موارد بشرية 2", "users.manage")
    other_user = _make_user("عضو عادي", "0599999602", hr_role.id)

    client = app.test_client()
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    client.post(f"/team/members/{other_user.id}/toggle")

    db.session.refresh(other_user)
    assert other_user.is_active_account is False, "المالك نفسه يقدر يعطّل أي حساب ثاني عادي"


def test_members_list_query_count_does_not_scale_with_member_count(app, owner):
    # كل عضو بدور *مختلف* عمداً — لو الكل بنفس role_id، الـidentity map
    # بـSQLAlchemy تخبّئ أول Role محمَّل وتعيد استخدامه للصفوف الباقية
    # حتى بدون joinedload، فيخفي خلل N+1 الحقيقي بدل ما يكشفه (نفس
    # الدرس المستفاد بفحوصات N+1 سابقة بهذي الجلسة).
    def _add_members(n, start):
        for i in range(start, start + n):
            role = _make_role_with_permission(f"دور اختبار N+1-{i}", "animals.view")
            _make_user(f"عضو {i}", f"05000097{i:02d}", role.id)

    client = app.test_client()
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})

    _add_members(3, 0)
    with count_queries() as small:
        client.get("/team/members")

    _add_members(20, 3)
    with count_queries() as big:
        client.get("/team/members")

    growth = big["n"] - small["n"]
    assert growth <= 3, (
        f"عدد الاستعلامات نما {growth} مع إضافة 20 عضو — يدل على خلل N+1 "
        f"(صغير={small['n']}, كبير={big['n']})"
    )
