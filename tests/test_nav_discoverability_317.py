"""بند إضافي 317 — طلبك: "راجع الواجهات من ناحية سهولة استخدام
المستخدم". فجوة اكتشاف حقيقية: شاشتا 'دفتر الملاحظات' (بند 298)
و'الإدخال الذكي' (بند 299) ما كانتا موجودتين إطلاقاً بالقائمة الجانبية
الرئيسية — الوصول الوحيد إليهما كان زرين صغيرين داخل شاشة المحادثة
نفسها، يعني مستخدم ما فتح المحادثة أول مرة ما يعرف إنهما موجودتان."""
from app.extensions import db
from app.models import Role, User


def _make_role_user(role_name, phone):
    role = Role.query.filter_by(name=role_name).first()
    user = User(name=f"مستخدم {role_name}", phone=phone, role_id=role.id, language="ar")
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_owner_sees_smart_entry_and_farm_notes_links_in_main_nav(app, client, owner):
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    resp = client.get("/")
    body = resp.data.decode()
    assert "دفتر الملاحظات" in body
    assert "الإدخال الذكي" in body


def test_worker_without_farm_notes_permission_does_not_see_that_link(app, client):
    """العامل الافتراضي يملك assistant.draft_actions.confirm بس ما
    يملك farm_notes.manage — لازم يشوف رابط 'الإدخال الذكي' بس مو
    'دفتر الملاحظات'."""
    worker = _make_role_user("worker", "0599999270")
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.get("/team/tasks")
    body = resp.data.decode()
    assert "الإدخال الذكي" in body
    assert "دفتر الملاحظات" not in body
