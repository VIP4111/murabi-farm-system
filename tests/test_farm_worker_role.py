"""بند إضافي — طلب صريح: مسمّى وظيفي جديد "عامل زراعي" منفصل عن
"العامل" الحالي، بدون صلاحيات مبدئياً (يحدّدها المالك بنفسه لاحقاً من
شاشة تعديل صلاحيات الدور)."""
from app.models import Role
from app.permissions_registry import DEFAULT_ROLES


def test_farm_worker_in_default_roles_registry():
    assert "farm_worker" in DEFAULT_ROLES
    assert DEFAULT_ROLES["farm_worker"]["display_name"] == "عامل زراعي"
    assert DEFAULT_ROLES["farm_worker"]["permissions"] == []


def test_farm_worker_role_created_by_seed(app):
    with app.app_context():
        role = Role.query.filter_by(name="farm_worker").first()
        assert role is not None
        assert role.display_label() == "عامل زراعي"
        assert role.permissions == []


def test_farm_worker_selectable_in_new_member_form(app, logged_in_client):
    resp = logged_in_client.get("/team/members/new")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert "عامل زراعي" in body
