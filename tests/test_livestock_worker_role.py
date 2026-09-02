"""بند إضافي — طلب صريح: مسمّى وظيفي "عامل تربية مواشي" يميّز رعاية
القطيع اليومية (تنظيف/تغذية/فحص) عن "عامل زراعي" (زراعة/أعلاف بس).
نفس الأسلوب: بدون صلاحيات مبدئياً، تُحدَّد لاحقاً يدوياً."""
from app.models import Role
from app.permissions_registry import DEFAULT_ROLES


def test_livestock_worker_in_default_roles_registry():
    assert "livestock_worker" in DEFAULT_ROLES
    assert DEFAULT_ROLES["livestock_worker"]["display_name"] == "عامل تربية مواشي"
    assert DEFAULT_ROLES["livestock_worker"]["permissions"] == []


def test_livestock_worker_role_created_by_seed(app):
    with app.app_context():
        role = Role.query.filter_by(name="livestock_worker").first()
        assert role is not None
        assert role.display_label() == "عامل تربية مواشي"
        assert role.permissions == []


def test_livestock_worker_selectable_in_new_member_form(app, logged_in_client):
    resp = logged_in_client.get("/team/members/new")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert "عامل تربية مواشي" in body
