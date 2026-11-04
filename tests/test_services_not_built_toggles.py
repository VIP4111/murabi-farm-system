"""بند إضافي 214 — مفاتيح الخدمات اللي ما لها ميزة فعلية خلفها تظهر "قيد البناء"
وما تنقلب، بدل زر تفعيل بلا أي أثر."""
from app.extensions import db
from app.models import ServiceToggle


def _make(key, name="خدمة"):
    s = ServiceToggle(key=key, name=name, is_enabled=False)
    db.session.add(s)
    db.session.commit()
    return s.id


def test_not_built_service_cannot_be_toggled(logged_in_client, app):
    with app.app_context():
        sid = _make("crm", "إدارة العملاء (CRM)")
    resp = logged_in_client.post(f"/settings/services/{sid}/toggle")
    assert resp.status_code == 302
    with app.app_context():
        assert ServiceToggle.query.get(sid).is_enabled is False


def test_working_service_still_toggles(logged_in_client, app):
    with app.app_context():
        sid = _make("dev_quick_login", "تسجيل دخول سريع")
    logged_in_client.post(f"/settings/services/{sid}/toggle")
    with app.app_context():
        assert ServiceToggle.query.get(sid).is_enabled is True


def test_settings_page_shows_under_construction_without_button(logged_in_client, app):
    with app.app_context():
        sid = _make("genetics", "الأنساب")
    html = logged_in_client.get("/settings").data.decode()
    assert "قيد البناء" in html
    assert f"/settings/services/{sid}/toggle" not in html
