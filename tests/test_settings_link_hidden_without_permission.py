"""بند إصلاح — بلاغ مستخدم: "المفروض كلمة الإعدادات تختفي لين أنا
أعطيه صلاحية" (بعد ما ضغط عليها بحساب الدكتور وطلعت له صفحة 403).
شريط التنقل الجانبي كان أصلاً يخفي رابط الإعدادات صح، لكن 3 شاشات
ثانية (التنبيهات، تقرير البيع الذكي، سجل التدقيق) فيها رابط/إشارة
لـ"الإعدادات" بدون فحص صلاحية `settings.manage` — تصل لها أدوار
تملك صلاحية الشاشة نفسها بس بدون صلاحية الإعدادات، فتشوف رابطاً
يوديها لصفحة ممنوعة. الإصلاح: يظهر الرابط فقط لمن يملك الصلاحية،
وإلا يبقى نص عادي غير قابل للضغط."""


def _make_doctor(app):
    from app.extensions import db
    from app.models import Role, User
    role = Role.query.filter_by(name="doctor").first()
    user = User(name="دكتور الاختبار", phone="0500000099", role_id=role.id, language="ar")
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_alerts_page_hides_settings_link_without_permission(app, client):
    with app.app_context():
        doctor = _make_doctor(app)
        phone = doctor.phone
    client.post("/login", data={"phone": phone, "password": "pass1234"})
    resp = client.get("/alerts")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'href="/settings"' not in body


def test_alerts_page_shows_settings_link_with_permission(app, logged_in_client):
    resp = logged_in_client.get("/alerts")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'href="/settings"' in body


def test_smart_sale_report_hides_settings_link_without_permission(app, client):
    with app.app_context():
        doctor = _make_doctor(app)
        phone = doctor.phone
    client.post("/login", data={"phone": phone, "password": "pass1234"})
    resp = client.get("/animals/smart-sale")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert 'href="/settings"' not in body
