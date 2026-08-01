"""بند إضافي 81 — أول إجراء بالمشروع بدون إعادة تحميل صفحة كاملة
(نقطة 7 من قائمة نقاط الضعف). زر "بدء" بجدول "مهامي" يرسل عبر fetch،
والصفحة تجلب جزء HTML مصغَّر بدل التنقّل الكامل. النموذج العادي
(بدون JS) يبقى يشتغل بالضبط زي قبل — هذي الاختبارات تتحقق من الاثنين."""
from app.team.task_service import assign_task


def test_task_start_ajax_returns_json_and_actually_starts_task(app, logged_in_client, owner):
    task = assign_task(actor=owner, title="مهمة اختبار بند81", assignee_id=owner.id)
    resp = logged_in_client.post(
        f"/team/tasks/{task.id}/start",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True}

    from app.models import Task
    assert Task.query.get(task.id).status == "in_progress"


def test_task_start_ajax_returns_400_on_business_error(app, logged_in_client, owner):
    task = assign_task(actor=owner, title="مهمة اختبار بند81ب", assignee_id=owner.id)
    # مهمة اتبدأت مسبقاً — تشغيلها ثانية يفشل منطقياً (TaskStateError)
    logged_in_client.post(f"/team/tasks/{task.id}/start")
    resp = logged_in_client.post(
        f"/team/tasks/{task.id}/start",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False
    assert body["error"]


def test_task_start_non_ajax_still_redirects_and_flashes(app, logged_in_client, owner):
    task = assign_task(actor=owner, title="مهمة اختبار بند81ج", assignee_id=owner.id)
    resp = logged_in_client.post(f"/team/tasks/{task.id}/start", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/team/tasks")


def test_my_tasks_fragment_returns_html_rows_only(app, logged_in_client, owner):
    assign_task(actor=owner, title="مهمة اختبار بند81د", assignee_id=owner.id)
    resp = logged_in_client.get("/team/tasks?fragment=my_tasks")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "مهمة اختبار بند81د" in body
    # ما يرجع صفحة كاملة — بدون <html>/<body>، جزء صفوف بس
    assert "<html" not in body
    assert "<body" not in body
