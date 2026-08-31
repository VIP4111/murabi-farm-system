"""بند إضافي (2026-08-31، طلبك المباشر: "ابيه شرح مكثف... اشروحات على
حسب الصلحيات المعطا فقط جوله كامله على حسب اللغه") — جولة تعريفية
مكثّفة أول دخول (`/onboarding/welcome`)، كل قسم فيها مربوط بصلاحية
فعلية (`user.has_permission`) بدل اسم الدور الثابت — تشتغل صح حتى لو
دور مخصَّص (permissions_customized) يملك تركيبة صلاحيات غير قياسية.
كل نص مغلَّف بـ_l() فيُترجم فعلياً حسب لغة الحساب."""
from app.extensions import db
from app.core import checklist_service
from app.models import Role, User, Permission


def _make_user(role_name, phone, language="ar"):
    role = Role.query.filter_by(name=role_name).first()
    u = User(name=f"مستخدم اختبار {role_name}", phone=phone, role_id=role.id, language=language)
    u.set_password("pass1234")
    db.session.add(u)
    db.session.commit()
    return u


def test_general_section_shown_to_everyone_regardless_of_permissions(app):
    from app.models import Role
    viewer_role = Role.query.filter_by(name="viewer").first()
    assert viewer_role is not None
    viewer = User(name="مشاهد اختبار", phone="0599999250", role_id=viewer_role.id)
    viewer.set_password("pass1234")
    db.session.add(viewer)
    db.session.commit()

    sections = checklist_service.permission_tour_sections(viewer)
    assert any(s["permission"] is None for s in sections)


def test_doctor_sees_health_and_repro_sections_but_not_finance_full(app):
    doctor = _make_user("doctor", "0599999251")
    sections = checklist_service.permission_tour_sections(doctor)
    perms_shown = {s["permission"] for s in sections}
    assert "health.manage" in perms_shown
    assert "repro.manage" in perms_shown
    assert "finance.full.manage" not in perms_shown  # الدكتور ما يملكها


def test_owner_sees_every_section(app):
    owner = _make_user("owner", "0599999252")
    sections = checklist_service.permission_tour_sections(owner)
    all_perms = {s["permission"] for s in checklist_service._TOUR_SECTIONS if s["permission"]}
    perms_shown = {s["permission"] for s in sections}
    assert all_perms.issubset(perms_shown)  # المالك يملك كل الصلاحيات


def test_custom_role_gets_sections_matching_its_actual_permissions_not_its_name(app):
    """الفحص الحاسم — دور مخصَّص باسم غريب («فني مستودع») يملك بس
    feed.view وequipment.view، ولازم يشوف قسمي العلف والمعدات بس، رغم
    إن اسمه ما يطابق أي دور افتراضي معروف بالكود."""
    perms = Permission.query.filter(Permission.code.in_(["feed.view", "equipment.view"])).all()
    role = Role(name="warehouse_tech_test", display_name="فني مستودع", is_system=False)
    role.permissions = perms
    db.session.add(role)
    db.session.commit()

    tech = User(name="فني اختبار", phone="0599999253", role_id=role.id)
    tech.set_password("pass1234")
    db.session.add(tech)
    db.session.commit()

    sections = checklist_service.permission_tour_sections(tech)
    perms_shown = {s["permission"] for s in sections if s["permission"]}
    assert perms_shown == {"feed.view", "equipment.view"}


def test_welcome_page_renders_tour_translated_for_english_user(app, client):
    doctor = _make_user("doctor", "0599999254", language="en")
    client.post("/login", data={"phone": doctor.phone, "password": "pass1234"})
    resp = client.get("/onboarding/welcome")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert "جولة مكثّفة" not in body
    assert "Intensive tour" in body or "intensive tour" in body.lower()


def test_settings_page_links_to_welcome_tour(app, logged_in_client):
    resp = logged_in_client.get("/settings")
    assert resp.status_code == 200
    assert '/onboarding/welcome' in resp.data.decode()
