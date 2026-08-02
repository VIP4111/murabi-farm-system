"""بند إضافي 91 (نقطة 8) — توسيع نمط AJAX من بند 81 (اللي كان مقصور
على زر "بدء" بس) ليشمل اعتماد/تأجيل/حذف المهام المقترحة بشاشة
"مهام مقترحة بانتظار الاعتماد". نفس نمط test_ajax_task_start.py بالضبط."""
from app.models import Task
from app.extensions import db


def _make_suggested_task(title="مهمة مقترحة اختبار بند91"):
    t = Task(title=title, task_type="custom", status="suggested")
    db.session.add(t)
    db.session.commit()
    return t


def test_task_approve_ajax_returns_json_and_actually_approves(app, logged_in_client, owner):
    task = _make_suggested_task()
    resp = logged_in_client.post(
        f"/team/tasks/{task.id}/approve",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True}
    assert Task.query.get(task.id).status == "pending"


def test_task_approve_ajax_returns_400_on_business_error(app, logged_in_client, owner):
    task = _make_suggested_task()
    logged_in_client.post(f"/team/tasks/{task.id}/approve")  # يعتمدها أول مرة (غير AJAX)
    resp = logged_in_client.post(
        f"/team/tasks/{task.id}/approve",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False
    assert body["error"]


def test_task_postpone_ajax_returns_json_and_actually_postpones(app, logged_in_client, owner):
    task = _make_suggested_task()
    old_due = task.due_date
    resp = logged_in_client.post(
        f"/team/tasks/{task.id}/postpone",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True}
    assert Task.query.get(task.id).due_date != old_due


def test_task_soft_delete_ajax_returns_json_and_actually_deletes(app, logged_in_client, owner):
    task = _make_suggested_task()
    resp = logged_in_client.post(
        f"/team/tasks/{task.id}/soft-delete",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True}
    assert Task.query.get(task.id).status == "deleted_pending_review"


def test_task_approve_non_ajax_still_redirects_and_flashes(app, logged_in_client, owner):
    task = _make_suggested_task()
    resp = logged_in_client.post(f"/team/tasks/{task.id}/approve", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/team/tasks")


def test_suggested_tasks_fragment_returns_html_rows_only(app, logged_in_client, owner):
    _make_suggested_task("مهمة اختبار جزء HTML بند91")
    resp = logged_in_client.get("/team/tasks?fragment=suggested_tasks")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "مهمة اختبار جزء HTML بند91" in body
    assert "<html" not in body
    assert "<body" not in body
