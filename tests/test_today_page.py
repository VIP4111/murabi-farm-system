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


def test_today_page_shows_full_farm_alerts_for_owner(app, owner, logged_in_client):
    """بند إضافي 136 — المالك/الدكتور عادةً ما هم "عامل مسؤول" رسمياً عن
    أي حظيرة (`_my_barn_ids` ترجع فاضية لهم)، فقبل هذا البند "صفحة
    اليوم" كانت تطلع فاضية من التنبيهات لهم دايماً رغم وجود تنبيهات
    حقيقية بالمزرعة — صار الحين يشوفون كل التنبيهات هنا، نفس شاشة
    "التنبيهات" القديمة بالضبط."""
    barn = Barn(barn_no="TODAY-B4", barn_name="حظيرة بدون مسؤول")
    db.session.add(barn)
    db.session.commit()

    resp = logged_in_client.get("/today")
    body = resp.data.decode()
    assert "حظيرة بدون مسؤول" in body


def test_today_page_alert_has_open_button(app, logged_in_client):
    """بند إضافي 138 — طلبك الصريح: "كل تنبيه تحط جنبه زر يحواني على
    المكان المقصود" — نفس زر "فتح" اللي كان بشاشة "التنبيهات" القديمة
    بالضبط، كان ناقص بـ"صفحة اليوم" بعد الدمج (بند 136)."""
    barn = Barn(barn_no="TODAY-B5", barn_name="حظيرة بدون مسؤول 2")
    db.session.add(barn)
    db.session.commit()

    resp = logged_in_client.get("/today")
    body = resp.data.decode()
    assert f'href="/barns/{barn.id}/edit"' in body


def test_sidebar_no_longer_links_to_separate_alerts_page(app, logged_in_client):
    resp = logged_in_client.get("/today")
    body = resp.data.decode()
    assert 'href="/alerts"' not in body
