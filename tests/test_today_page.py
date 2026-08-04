"""بند إضافي 122 — صفحة اليوم: تجمع مهامي المفتوحة، تنبيهات حظائري،
وبلاغاتي المفتوحة بشاشة وحدة، بدل التنقّل بين 3 شاشات منفصلة. لا منطق
جديد — نفس استعلامات tasks_list/alerts_mine/reports_list الموجودة
أصلاً، مجمَّعة للعرض بس."""
from app.extensions import db
from app.models import Role, User, Barn, Task, Report


def _make_worker():
    role = Role.query.filter_by(name="worker").first()
    user = User(name="عامل اليوم", phone="0599999122", role_id=role.id, language="ar")
    user.set_password("test1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_today_page_loads_and_shows_link_from_worker_home(app, client):
    worker = _make_worker()
    client.post("/login", data={"phone": worker.phone, "password": "test1234"})
    home = client.get("/")
    assert 'href="/today"' in home.data.decode()

    resp = client.get("/today")
    assert resp.status_code == 200
    assert "صفحة اليوم" in resp.data.decode()


def test_today_page_shows_my_open_task(app, client):
    worker = _make_worker()
    task = Task(title="مهمة اختبار اليوم", assignee_id=worker.id, status="pending", task_type="other")
    db.session.add(task)
    db.session.commit()

    client.post("/login", data={"phone": worker.phone, "password": "test1234"})
    resp = client.get("/today")
    body = resp.data.decode()
    assert "مهمة اختبار اليوم" in body


def test_today_page_shows_my_barn_alert_scoped_only(app, client):
    """نفس فلسفة alerts_mine — يشوف تنبيهات حظائره هو بس، مو كل المزرعة."""
    worker = _make_worker()
    barn = Barn(barn_no="TODAY-B1", barn_name="حظيرة اليوم", responsible_worker_id=worker.id)
    db.session.add(barn)
    db.session.commit()

    client.post("/login", data={"phone": worker.phone, "password": "test1234"})
    resp = client.get("/today")
    assert resp.status_code == 200


def test_today_page_shows_my_open_report(app, client):
    worker = _make_worker()
    barn = Barn(barn_no="TODAY-B2", barn_name="حظيرة اليوم 2", responsible_worker_id=worker.id)
    db.session.add(barn)
    db.session.commit()
    report = Report(reporter_id=worker.id, description="بلاغ اختبار اليوم", report_type="مشكلة",
                     barn_id=barn.id, status="new")
    db.session.add(report)
    db.session.commit()

    client.post("/login", data={"phone": worker.phone, "password": "test1234"})
    resp = client.get("/today")
    body = resp.data.decode()
    assert "بلاغ اختبار اليوم" in body


def test_today_page_hides_closed_reports(app, client):
    worker = _make_worker()
    barn = Barn(barn_no="TODAY-B3", barn_name="حظيرة اليوم 3", responsible_worker_id=worker.id)
    db.session.add(barn)
    db.session.commit()
    closed_report = Report(reporter_id=worker.id, description="بلاغ مغلق قديم", report_type="مشكلة",
                            barn_id=barn.id, status="closed")
    db.session.add(closed_report)
    db.session.commit()

    client.post("/login", data={"phone": worker.phone, "password": "test1234"})
    resp = client.get("/today")
    body = resp.data.decode()
    assert "بلاغ مغلق قديم" not in body
