"""اختبار بند الفحص العميق الجديد — 3 أخطاء حقيقية:
1. FAMILY_VIEW_ROLES (شاشة المتابعة المبسّطة) كانت نصوصاً عربية خاماً
   غير قابلة للترجمة.
2. family_view.html كان يعرض كود سبب تعذّر المهمة الخام (مثل
   no_stock) بدل ترجمته، عكس task_detail.html اللي يترجمه صح.
3. رسالة تنبيه الإجهاد الحراري بشاشة المناخ كانت f-string خام، ما
   تمر على gettext إطلاقاً."""
from datetime import date

from app.extensions import db
from app.models import Role, Task, User


def _make_english_client(client):
    role = Role.query.filter_by(name="owner").first()
    user = User(name="English Owner", phone="0500009100", role_id=role.id, language="en")
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    client.post("/login", data={"phone": user.phone, "password": "pass1234"})
    return client


def test_family_view_role_labels_translate_to_english(client):
    en_client = _make_english_client(client)
    resp = en_client.get("/family-view")
    assert resp.status_code == 200
    assert b"Owner's tasks" in resp.data
    assert "مهام صاحب الحلال".encode() not in resp.data


def test_family_view_translates_failure_reason(client):
    en_client = _make_english_client(client)
    owner = User.query.filter_by(phone="0500009100").first()
    task = Task(title="مهمة اختبار", status="failed", assignee_id=owner.id,
                failure_reason="نقص الأدوات")
    from datetime import datetime, timezone
    task.failed_at = datetime.now(timezone.utc)
    db.session.add(task)
    db.session.commit()

    resp = en_client.get("/family-view")
    assert resp.status_code == 200
    assert b"Missing tools" in resp.data
    assert "نقص الأدوات".encode() not in resp.data


def test_climate_heat_stress_flash_translates_to_english(client, monkeypatch):
    from app.climate import routes as climate_routes
    from tests.factories import make_weather_reading

    en_client = _make_english_client(client)
    fake_task = Task(title="فحص إجهاد حراري", status="suggested")
    db.session.add(fake_task)
    db.session.commit()
    reading = make_weather_reading(date.today())

    monkeypatch.setattr(climate_routes.svc, "get_forecast", lambda: {
        "configured": True, "readings": [reading],
    })
    monkeypatch.setattr(climate_routes.svc, "generate_heat_checklists", lambda readings: [fake_task])

    resp = en_client.get("/climate/", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Heat stress forecast" in resp.data
    assert "توقّع إجهاد حراري".encode() not in resp.data
