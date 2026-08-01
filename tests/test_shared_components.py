"""بند إضافي 80 — أول مكوّن Jinja مشترك حقيقي بالمشروع (نقطة 6 من
قائمة نقاط الضعف: إعادة استخدام المكوّنات). status_badge() بـ
_macros.html بدل تكرار بنية <span class="badge" data-state="..."> يدوياً
بكل قالب."""


def test_status_badge_state_filter_covers_common_statuses(app):
    filt = app.jinja_env.filters["status_badge_state"]
    assert filt("active") == "active"
    assert filt("pending") == "pending"
    assert filt("done") == "completed"
    assert filt("failed") == "overdue"
    assert filt("cancelled") == "cancelled"
    assert filt("sold") == "completed"
    assert filt("dead") == "cancelled"
    assert filt("some_unknown_future_status") == "pending"


def test_reports_list_uses_shared_status_badge_macro(app, logged_in_client):
    from app.models import Report, User
    from app.extensions import db

    owner = User.query.filter_by(phone="0500000001").first()
    r = Report(reporter_id=owner.id, description="اختبار بند 80", status="new")
    db.session.add(r)
    db.session.commit()

    resp = logged_in_client.get("/team/reports")
    assert b'class="badge" data-state="pending"' in resp.data


def test_diseases_list_uses_shared_status_badge_macro(app, logged_in_client):
    from app.models import Disease
    from app.extensions import db
    from datetime import date
    from tests.factories import make_animal

    animal = make_animal()
    db.session.add(animal)
    db.session.commit()
    d = Disease(animal_id=animal.id, date=date.today(), disease_name="اختبار",
                status="active")
    db.session.add(d)
    db.session.commit()

    resp = logged_in_client.get("/health/diseases")
    assert b'class="badge" data-state="active"' in resp.data
