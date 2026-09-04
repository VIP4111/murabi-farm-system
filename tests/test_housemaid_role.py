"""بند إضافي — طلب صريح: "ابيك تضيف عامله منزليه بدون مميزات او ربط
فقط تظيفها في ارواتب" — مسمّى وظيفي جديد بصفر صلاحيات عمداً (نفس نمط
الأدوار السابقة: عامل زراعي/عامل بناء/مدير مزرعة/عامل تربية مواشي)،
الهدف الوحيد ظهورها كخيار بشاشة الرواتب/الأعضاء."""
from app.models import Role
from app.permissions_registry import DEFAULT_ROLES


def test_housemaid_in_default_roles_registry():
    assert "housemaid" in DEFAULT_ROLES
    assert DEFAULT_ROLES["housemaid"]["display_name"] == "عاملة منزلية"
    assert DEFAULT_ROLES["housemaid"]["permissions"] == []


def test_housemaid_role_created_by_seed(app):
    with app.app_context():
        role = Role.query.filter_by(name="housemaid").first()
        assert role is not None
        assert role.display_label() == "عاملة منزلية"
        assert role.permissions == []


def test_housemaid_selectable_in_new_member_form(app, logged_in_client):
    resp = logged_in_client.get("/team/members/new")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert "عاملة منزلية" in body
