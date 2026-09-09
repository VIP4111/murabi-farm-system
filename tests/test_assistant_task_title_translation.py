"""بند إصلاح (فحص عميق — طلبك: "افحص شاشة المساعد الذكي كمان") —
`context_service.my_tasks_summary()` كانت ترجع `t.title` الخام دايماً
لردود المساعد الذكي ("مهامي اليوم"/"شنو أسوي اليوم")، نفس فجوة عناوين
المهام اليومية التلقائية اللي أُصلحت لشاشات القوائم لكن نُسيت هنا."""
from app.extensions import db
from app.models import Role, User
from app.models.task import Task
from app.assistant import context_service
from flask_babel import force_locale


def test_my_tasks_summary_translates_daily_task_title(app):
    role = Role.query.filter_by(name="worker").first()
    worker = User(name="W", phone="0500099701", role_id=role.id, language="en")
    worker.set_password("pass1234")
    db.session.add(worker)
    db.session.flush()
    task = Task(title="🚧 مراجعة العزل والحجر", task_type="daily_husbandry",
                title_key="daily_isolation_review", status="pending", assignee_id=worker.id)
    db.session.add(task)
    db.session.commit()

    with force_locale("en"):
        summary = context_service.my_tasks_summary(worker)
    assert summary["count"] == 1
    assert "Isolation" in summary["items"][0]["title"]
