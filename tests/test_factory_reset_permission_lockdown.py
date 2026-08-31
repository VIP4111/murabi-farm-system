"""بند إضافي (2026-08-31، طلبك المباشر) — ثغرة حقيقية: صلاحية
"ضبط المصنع" (system.factory_reset) كانت تظهر كمربّع عادي بشاشة "تعديل
صلاحيات الدور"، تقدر تُؤشَّر لأي دور ثانٍ رغم إن التصميم الأصلي يفترضها
حصرية لصاحب الحلال دائماً (تعليق app/permissions_registry.py). الفحص
الفعلي بالراوت (`@require_permission`) كان يثق بالصلاحية المخزَّنة بس،
بدون أي حماية إضافية لو انفتحت بالغلط.

الإصلاح (دفاع بعمق، طبقتين):
1. شاشة تعديل صلاحيات الدور ما تعرض/تقبل system.factory_reset إطلاقاً
   لأي دور — تُحذف من القائمة المعروضة، وتُتجاهَل حتى لو أُرسلت يدوياً
   بالفورم.
2. راوت /settings/factory-reset نفسه صار يفحص current_user.role.name
   == "owner" مباشرة، مو بس الصلاحية — حتى لو انفتحت الصلاحية لدور ثانٍ
   بأي طريقة (بيانات قديمة، تعديل مباشر بقاعدة البيانات...)، التنفيذ
   الفعلي يبقى محجوباً."""
from app.extensions import db
from app.models import Permission, Role, User
from app.core.routes import FACTORY_RESET_CONFIRM_PHRASE


def test_factory_reset_not_offered_in_role_edit_screen(app, logged_in_client):
    doctor = Role.query.filter_by(name="doctor").first()
    resp = logged_in_client.get(f"/settings/roles/{doctor.id}/edit")
    assert resp.status_code == 200
    assert b"system.factory_reset" not in resp.data


def test_role_edit_ignores_factory_reset_even_if_submitted_manually(app, logged_in_client):
    doctor = Role.query.filter_by(name="doctor").first()
    resp = logged_in_client.post(f"/settings/roles/{doctor.id}/edit", data={
        "display_name": doctor.display_name,
        "permissions": ["animals.view", "health.view", "system.factory_reset"],
    })
    assert resp.status_code in (302, 303)
    db.session.refresh(doctor)
    codes = {p.code for p in doctor.permissions}
    assert "system.factory_reset" not in codes
    assert "animals.view" in codes  # باقي الصلاحيات المطلوبة اتحفظت طبيعي


def test_factory_reset_route_blocked_even_if_permission_granted_directly(app, client):
    """محاكاة أسوأ سيناريو: صلاحية system.factory_reset انفتحت لدور غير
    المالك بأي طريقة (تعديل مباشر بقاعدة البيانات مثلاً، متجاوزة شاشة
    تعديل الصلاحيات كلياً). الفحص الحصري بالراوت لازم يمنع التنفيذ
    برضو."""
    role = Role.query.filter_by(name="doctor").first()
    perm = Permission.query.filter_by(code="system.factory_reset").first()
    role.permissions = list(role.permissions) + [perm]
    db.session.commit()

    doctor = User(name="دكتور اختبار ضبط المصنع", phone="0599999240", role_id=role.id)
    doctor.set_password("pass1234")
    db.session.add(doctor)
    db.session.commit()
    assert doctor.has_permission("system.factory_reset") is True  # الصلاحية فعلاً موجودة له

    client.post("/login", data={"phone": doctor.phone, "password": "pass1234"})
    resp = client.post("/settings/factory-reset", data={
        "confirm_phrase": FACTORY_RESET_CONFIRM_PHRASE, "password": "pass1234",
    })
    assert resp.status_code == 403
