"""بند إضافي 107 — "مهام العامل التلقائية": قوالب المهام اليومية الثابتة
صارت بيانات بقاعدة البيانات (قابلة للإضافة/الإيقاف من الواجهة)، وتوصل
للعامل تلقائياً بدون انتظار اعتماد الدكتور. وتصحيح فجوة مرتبطة: مهمة
يومية بلا عامل محدد كانت ما تظهر لأي عامل حتى بعد اعتمادها."""
from datetime import date, datetime, timedelta

from app.extensions import db
from app.core import daily_task_service as svc
from app.models import DailyTaskTemplate, Task
from app.team import task_service as tsvc

MORNING = datetime.combine(date.today(), datetime.min.time()) + timedelta(hours=9)


def test_deactivated_template_stops_generating_tasks(app):
    t = DailyTaskTemplate.query.filter_by(title="🧹 تنظيف المعالف والحظائر").first()
    t.is_active = False
    db.session.commit()

    created = svc.generate_daily_husbandry_tasks(now=MORNING)
    assert not any(c.title == "🧹 تنظيف المعالف والحظائر" for c in created)


def test_new_template_generates_task_immediately(app):
    db.session.add(DailyTaskTemplate(title="🐑 عدّ رؤوس القطيع", notes="عدّ يومي", sort_order=99))
    db.session.commit()

    created = svc.generate_daily_husbandry_tasks(now=MORNING)
    assert any(c.title == "🐑 عدّ رؤوس القطيع" for c in created)


def test_unassigned_worker_task_visible_in_role_matching_worker_list(app, client, worker):
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    svc.generate_daily_husbandry_tasks(now=MORNING)

    resp = client.get("/team/tasks")
    assert "🧹 تنظيف المعالف والحظائر" in resp.data.decode()


def test_worker_can_view_unassigned_role_matching_task_detail(app, client, worker):
    created = svc.generate_daily_husbandry_tasks(now=MORNING)
    task = next(t for t in created if t.title == "🔍 فحص يومي للقطيع" and t.due_date == date.today())

    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.get(f"/team/tasks/{task.id}")
    assert resp.status_code == 200


def test_starting_unassigned_task_claims_it_for_actor(app, worker):
    created = svc.generate_daily_husbandry_tasks(now=MORNING)
    task = next(t for t in created if t.title == "💧 فحص الماء والأملاح" and t.due_date == date.today())
    assert task.assignee_id is None

    tsvc.start_task(task, actor=worker)
    db.session.refresh(task)
    assert task.assignee_id == worker.id
    assert task.status == "in_progress"


def test_daily_template_toggle_route(app, logged_in_client):
    t = DailyTaskTemplate.query.first()
    resp = logged_in_client.post(f"/team/tasks/daily-templates/{t.id}/toggle")
    assert resp.status_code == 302
    db.session.refresh(t)
    assert t.is_active is False


def test_daily_template_create_route(app, logged_in_client):
    resp = logged_in_client.post("/team/tasks/daily-templates", data={
        "title": "🌾 فحص مخزون العلف", "notes": "تأكد الكمية كافية لليوم",
    })
    assert resp.status_code == 302
    assert DailyTaskTemplate.query.filter_by(title="🌾 فحص مخزون العلف").first() is not None
