"""اختبارات نافذة "توزيع مهمة" المنبثقة (بند إضافي 69): نفس منطق
الراوت السابق (تعيين مباشر)، بس بواجهة منبثقة + دعم target_role."""
from app.extensions import db
from app.models import Task, Role, User


def test_tasks_list_page_contains_modal_markup_not_link(app, logged_in_client):
    resp = logged_in_client.get("/team/tasks")
    assert resp.status_code == 200
    assert b'id="assignTaskModal"' in resp.data
    assert b'id="openAssignTaskModalBtn"' in resp.data


def test_assign_task_with_target_role_saves_it(app, logged_in_client):
    resp = logged_in_client.post("/team/tasks/new", data={
        "title": "مهمة بدور مستهدف", "task_type": "custom", "target_role": "accountant",
    }, follow_redirects=True)
    assert resp.status_code == 200
    task = Task.query.filter_by(title="مهمة بدور مستهدف").one()
    assert task.target_role == "accountant"


def test_assign_task_without_target_role_still_works(app, logged_in_client):
    resp = logged_in_client.post("/team/tasks/new", data={
        "title": "مهمة بدون دور", "task_type": "custom",
    }, follow_redirects=True)
    assert resp.status_code == 200
    task = Task.query.filter_by(title="مهمة بدون دور").one()
    assert task.target_role is None


def test_assignee_options_carry_role_data_attribute(app, logged_in_client):
    role = Role.query.filter_by(name="worker").first()
    worker = User(name="عامل بدور", phone="0500000098", role_id=role.id,
                  language="ar", is_active_account=True)
    worker.set_password("pass1234")
    db.session.add(worker)
    db.session.commit()

    resp = logged_in_client.get("/team/tasks")
    assert resp.status_code == 200
    assert f'data-role="worker">{worker.name}'.encode() in resp.data


def test_full_page_form_still_works_as_fallback(app, logged_in_client):
    """الصفحة الكاملة القديمة (team/task_form.html) لازم تبقى تشتغل —
    الاحتياط لو صار خطأ إدخال بالنافذة المنبثقة."""
    resp = logged_in_client.get("/team/tasks/new")
    assert resp.status_code == 200
    assert "توزيع مهمة جديدة".encode() in resp.data
