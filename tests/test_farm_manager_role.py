"""بند إضافي — طلب صريح: مسمّى وظيفي جديد "مدير مزرعة" (نفس أسلوب
"عامل زراعي" و"عامل بناء" السابقين)، بدون صلاحيات مبدئياً (يحدّدها
المالك بنفسه لاحقاً من شاشة تعديل صلاحيات الدور)."""
from app.models import Role
from app.permissions_registry import DEFAULT_ROLES


def test_farm_manager_in_default_roles_registry():
    assert "farm_manager" in DEFAULT_ROLES
    assert DEFAULT_ROLES["farm_manager"]["display_name"] == "مدير مزرعة"
    assert DEFAULT_ROLES["farm_manager"]["permissions"] == []


def test_farm_manager_role_created_by_seed(app):
    with app.app_context():
        role = Role.query.filter_by(name="farm_manager").first()
        assert role is not None
        assert role.display_label() == "مدير مزرعة"
        assert role.permissions == []


def test_farm_manager_selectable_in_new_member_form(app, logged_in_client):
    resp = logged_in_client.get("/team/members/new")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert "مدير مزرعة" in body
