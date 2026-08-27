"""بند إضافي 280 — طلبك الصريح: "المهام المقترحة المفروض تطلع بتاريخ
جديد مثل اليوم 28 تطلع لي مقترحات فقط لتاريخ 28 و29، إذا اعتمدت 28
المفروض تختفي، ولو عديت ودخلت 30 بدون اعتماد 28 تنحذف تلقائي"."""
from datetime import date, timedelta

from app.extensions import db
from app.models import Task
from app.team import task_service as tsvc
from factories import make_barn

TODAY = date.today()


def _suggested(title, due_date, barn=None):
    t = Task(title=title, task_type="custom", status="suggested", due_date=due_date,
             barn_id=barn.id if barn else None)
    db.session.add(t)
    db.session.commit()
    return t


def test_tasks_list_shows_only_today_and_tomorrow(app, logged_in_client):
    barn = make_barn(barn_no="SW-01")
    today_task = _suggested("مهمة اليوم", TODAY, barn)
    tomorrow_task = _suggested("مهمة بكرة", TODAY + timedelta(days=1), barn)
    later_task = _suggested("مهمة بعدين", TODAY + timedelta(days=5), barn)

    resp = logged_in_client.get("/team/tasks?fragment=suggested_tasks")
    body = resp.data.decode()
    assert today_task.title in body
    assert tomorrow_task.title in body
    assert later_task.title not in body


def test_tasks_without_due_date_always_shown(app, logged_in_client):
    """مهام مقترحة بلا موعد محدد (نادرة، زي بعض خطط العلاج) ما فيها
    تاريخ نقارنه أصلاً — تبقى تظهر دايماً."""
    t = _suggested("مهمة بلا موعد", None)
    resp = logged_in_client.get("/team/tasks?fragment=suggested_tasks")
    assert t.title in resp.data.decode()


def test_expire_stale_suggested_tasks_deletes_after_two_days_overdue(app):
    barn = make_barn(barn_no="SW-02")
    two_days_overdue = _suggested("مهمة انتهت صلاحيتها", TODAY - timedelta(days=2), barn)
    one_day_overdue = _suggested("مهمة متأخرة يوم بس", TODAY - timedelta(days=1), barn)

    expired = tsvc.expire_stale_suggested_tasks(today=TODAY)

    assert two_days_overdue.id in [t.id for t in expired]
    assert one_day_overdue.id not in [t.id for t in expired]
    db.session.refresh(two_days_overdue)
    db.session.refresh(one_day_overdue)
    assert two_days_overdue.status == "deleted_pending_review"
    assert one_day_overdue.status == "suggested"


def test_expired_task_lands_in_owner_review_box(app):
    barn = make_barn(barn_no="SW-03")
    t = _suggested("مهمة راح تنحذف تلقائي", TODAY - timedelta(days=3), barn)
    tsvc.expire_stale_suggested_tasks(today=TODAY)
    db.session.refresh(t)
    assert t.status == "deleted_pending_review"
    assert "انتهت صلاحيتها تلقائياً" in t.notes


def test_visiting_tasks_list_triggers_auto_expiry(app, logged_in_client):
    barn = make_barn(barn_no="SW-04")
    t = _suggested("مهمة قديمة جداً", TODAY - timedelta(days=10), barn)
    resp = logged_in_client.get("/team/tasks?fragment=suggested_tasks")
    assert t.title not in resp.data.decode()
    db.session.refresh(t)
    assert t.status == "deleted_pending_review"


def test_approving_today_task_makes_it_disappear_from_suggested_list(app, logged_in_client, owner):
    barn = make_barn(barn_no="SW-05")
    t = _suggested("مهمة تُعتمد اليوم", TODAY, barn)
    tsvc.approve_suggested_task(t, actor=owner)
    resp = logged_in_client.get("/team/tasks")
    body = resp.data.decode()
    assert "مهام مقترحة بانتظار الاعتماد" in body
    assert t.status == "pending"
