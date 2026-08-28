"""بند إضافي 295 — طلبك "ابحث وحل المشكلة بدون توقف": نفس فجوة
"المزارع" (بند 293/294) بمكان رابع. الصفحة الرئيسية كانت توجّه للواجهة
المبسّطة بفحص `role.name == "worker"` الحرفي — أي مسمّى وظيفي مخصَّص
مستنسخ من صلاحيات عامل (زي "المزارع") كان يشوف اللوحة العامة المعقّدة
بدل الواجهة المبسّطة اللي بُنيت له أصلاً. صار الفحص بغياب صلاحية
`animals.view` (نفس معيار بند 46)."""
from app.extensions import db
from app.models import Role, Permission, User


def _make_custom_worker_role(name="المزارع"):
    perm_codes = ("tasks.view_own", "reports.submit", "assistant.use")
    perms = Permission.query.filter(Permission.code.in_(perm_codes)).all()
    role = Role(name=name, display_name=name, is_system=False)
    role.permissions = perms
    db.session.add(role)
    db.session.commit()
    return role


def test_custom_role_cloned_from_worker_gets_simplified_home(app, client):
    role = _make_custom_worker_role()
    user = User(name="مزارع اختبار", phone="0599999170", role_id=role.id)
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()

    client.post("/login", data={"phone": user.phone, "password": "pass1234"})
    resp = client.get("/")
    assert resp.status_code == 200
    # نص فريد بواجهة العامل المبسّطة (worker_home.html) بس.
    assert "اختر الإجراء اللي تبي تسجّله".encode() in resp.data


def test_accountant_still_gets_full_dashboard(app, client, owner):
    """أهم فحص عكسي: المحاسب عنده animals.view أصلاً — ما يفترض يتأثر
    بهذا التغيير ويبقى يشوف اللوحة العامة."""
    role = Role.query.filter_by(name="accountant").first()
    user = User(name="محاسب اختبار", phone="0599999171", role_id=role.id)
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()

    client.post("/login", data={"phone": user.phone, "password": "pass1234"})
    resp = client.get("/")
    assert resp.status_code == 200
    assert "اختر الإجراء اللي تبي تسجّله".encode() not in resp.data


def test_setup_checklist_dismiss_checks_permission_not_role_name(app, client):
    """بند إضافي 295 — نفس الشاشة: صار يفحص `settings.manage` بدل
    اسم الدور "owner" الحرفي."""
    role = _make_custom_worker_role(name="سوبر مساعد")
    perm = Permission.query.filter_by(code="settings.manage").first()
    role.permissions = [perm]
    db.session.commit()

    user = User(name="مساعد إعدادات", phone="0599999172", role_id=role.id)
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()

    client.post("/login", data={"phone": user.phone, "password": "pass1234"})
    resp = client.post("/setup-checklist/dismiss")
    assert resp.status_code == 302  # نجح، ما رجع 403
