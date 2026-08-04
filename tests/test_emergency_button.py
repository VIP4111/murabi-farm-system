"""بند إضافي 121 — زر طوارئ عائم بكل الشاشات، يفتح مباشرة بلاغ "حالة
طارئة" (فئة جديدة بمحرك worker_quick_report الموجود أصلاً، بدون أي
منطق جديد) بدل ما يدور المستخدم بالقائمة الجانبية وقت طارئ فعلي."""
from app.extensions import db
from app.models import Role, User, Report, Barn


def _make_worker():
    role = Role.query.filter_by(name="worker").first()
    user = User(name="عامل طوارئ", phone="0500000097", role_id=role.id, language="ar")
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_emergency_fab_appears_on_every_authenticated_page(app, client):
    worker = _make_worker()
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.get("/team/tasks")
    body = resp.data.decode()
    assert '<a class="emergency-fab"' in body
    assert "/team/worker/report/emergency" in body


def test_emergency_fab_hidden_on_its_own_page(app, client):
    worker = _make_worker()
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.get("/team/worker/report/emergency")
    body = resp.data.decode()
    assert '<a class="emergency-fab"' not in body


def test_emergency_report_submits_with_correct_type(app, client):
    worker = _make_worker()
    barn = Barn(barn_no="EMG-B1", barn_name="حظيرة الطوارئ", responsible_worker_id=worker.id)
    db.session.add(barn)
    db.session.commit()
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.post("/team/worker/report/emergency", data={
        "barn_id": str(barn.id), "description": "حيوان بحالة حرجة",
    })
    assert resp.status_code == 302
    report = Report.query.filter_by(reporter_id=worker.id).first()
    assert report is not None
    assert report.report_type == "حالة طارئة"


def test_emergency_category_translates_for_amharic_worker(app, client):
    role = Role.query.filter_by(name="worker").first()
    worker = User(name="عامل أمهري طوارئ", phone="0500000096", role_id=role.id, language="am")
    worker.set_password("pass1234")
    db.session.add(worker)
    db.session.commit()
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.get("/")
    body = resp.data.decode()
    assert "አስቸኳይ ሁኔታ" in body
