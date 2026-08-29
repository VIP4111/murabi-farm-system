"""بند إضافي 317 — طلبك: "راجع الواجهات من ناحية سهولة استخدام
المستخدم". فجوة اكتشاف حقيقية: شاشتا 'دفتر الملاحظات' (بند 298)
و'الإدخال الذكي' (بند 299) ما كانتا موجودتين إطلاقاً بالقائمة الجانبية
الرئيسية — الوصول الوحيد إليهما كان زرين صغيرين داخل شاشة المحادثة
نفسها، يعني مستخدم ما فتح المحادثة أول مرة ما يعرف إنهما موجودتان.

**تحديث بند إضافي 318**: الثلاث شاشات (محادثة/ملاحظات/إدخال ذكي) صارت
مدمجة بصفحة واحدة بتبويبات — القائمة الجانبية صار فيها رابط واحد
'مركز الذكاء الاصطناعي' بدل الروابط الثلاث المنفصلة، والتمييز
بالصلاحيات صار داخل الصفحة نفسها (ظهور/اختفاء التبويب)."""
from app.extensions import db
from app.models import Role, User


def _make_role_user(role_name, phone):
    role = Role.query.filter_by(name=role_name).first()
    user = User(name=f"مستخدم {role_name}", phone=phone, role_id=role.id, language="ar")
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_owner_sees_ai_hub_link_in_main_nav(app, client, owner):
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    resp = client.get("/")
    body = resp.data.decode()
    assert "مركز الذكاء الاصطناعي" in body


def test_hub_page_shows_notes_tab_only_with_permission(app, client, owner):
    """المالك يملك farm_notes.manage — تبويب دفتر الملاحظات لازم يظهر
    داخل مركز الذكاء الاصطناعي نفسه."""
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    resp = client.get("/assistant/")
    body = resp.data.decode()
    assert "دفتر الملاحظات" in body
    assert "الإدخال الذكي" in body


def test_hub_page_hides_notes_tab_without_permission(app, client):
    """العامل الافتراضي يملك assistant.draft_actions.confirm بس ما
    يملك farm_notes.manage — تبويب دفتر الملاحظات ما يظهر له، بس
    تبويب الإدخال الذكي يظهر."""
    worker = _make_role_user("worker", "0599999270")
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.get("/assistant/")
    body = resp.data.decode()
    assert "الإدخال الذكي" in body
    assert "دفتر الملاحظات" not in body
