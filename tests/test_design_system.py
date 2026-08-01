"""بند إضافي 76 — الطبقة التأسيسية من نظام تصميم claude.ai/design
(توكِنز، شارة حالة موحّدة، كثافة عرض العامل). CSS إضافي بس — بدون
تغيير أي قيمة/سلوك موجود، فالاختبارات هنا تتحقق من الإضافات الجديدة
فقط."""
from app.team.task_service import assign_task
from app.models import Role, User
from app.extensions import db


def test_task_badge_state_filter_maps_known_and_unknown_values(app):
    filt = app.jinja_env.filters["task_badge_state"]
    assert filt("pending") == "pending"
    assert filt("in_progress") == "active"
    assert filt("done") == "completed"
    assert filt("failed") == "overdue"
    assert filt("cancelled") == "cancelled"
    assert filt("some_future_status_not_mapped_yet") == "pending"


def _make_worker():
    role = Role.query.filter_by(name="worker").first()
    user = User(name="عامل اختبار 76", phone="0500009922", role_id=role.id, language="ar")
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_worker_main_gets_comfortable_density_attribute(app, client):
    worker = _make_worker()
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.get("/")
    assert b'<main data-density="comfortable">' in resp.data


def test_owner_main_does_not_get_comfortable_density_attribute(app, logged_in_client):
    resp = logged_in_client.get("/")
    assert b'<main data-density="comfortable">' not in resp.data
    assert b"<main>" in resp.data


def test_tasks_list_status_uses_unified_badge_component(app, logged_in_client, owner):
    assign_task(actor=owner, title="مهمة اختبار بند 76", assignee_id=owner.id)
    resp = logged_in_client.get("/team/tasks")
    assert b'class="badge" data-state="pending"' in resp.data
