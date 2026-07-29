"""اختبارات فلترة المهام المقترحة حسب الدور المستهدف (بند إضافي 68)."""
from app.extensions import db
from app.models import Task, Role, User


def _make_user_with_role(role_name, phone):
    role = Role.query.filter_by(name=role_name).first()
    user = User(name=f"مستخدم {role_name}", phone=phone, role_id=role.id, language="ar")
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_daily_husbandry_tasks_get_worker_target_role(app):
    from app.core import daily_task_service
    daily_task_service.generate_daily_husbandry_tasks()
    tasks = Task.query.filter_by(source_type="DailyHusbandry").all()
    assert tasks
    assert all(t.target_role == "worker" for t in tasks)


def test_role_filter_shows_only_matching_target_role(app, logged_in_client):
    t_worker = Task(title="مهمة عامل", task_type="custom", status="suggested", target_role="worker")
    t_doctor = Task(title="مهمة طبيب", task_type="custom", status="suggested", target_role="doctor")
    db.session.add_all([t_worker, t_doctor])
    db.session.commit()

    resp = logged_in_client.get("/team/tasks?role=worker")
    assert resp.status_code == 200
    assert "مهمة عامل".encode() in resp.data
    assert "مهمة طبيب".encode() not in resp.data


def test_role_filter_all_shows_everything(app, logged_in_client):
    t_worker = Task(title="مهمة عامل 2", task_type="custom", status="suggested", target_role="worker")
    t_doctor = Task(title="مهمة طبيب 2", task_type="custom", status="suggested", target_role="doctor")
    db.session.add_all([t_worker, t_doctor])
    db.session.commit()

    resp = logged_in_client.get("/team/tasks?role=all")
    assert resp.status_code == 200
    assert "مهمة عامل 2".encode() in resp.data
    assert "مهمة طبيب 2".encode() in resp.data


def test_role_filter_falls_back_to_assignee_role_when_no_target_role(app, logged_in_client):
    """مهمة قديمة (قبل بند 68) بدون target_role — لازم تظهر بفلتر دور
    الشخص المعيّن لها فعلياً، بدل ما تختفي تماماً."""
    doctor = _make_user_with_role("doctor", "0500000099")
    t = Task(title="مهمة مُعيَّنة لدكتور بدون target_role", task_type="custom",
             status="suggested", assignee_id=doctor.id, target_role=None)
    db.session.add(t)
    db.session.commit()

    resp = logged_in_client.get("/team/tasks?role=doctor")
    assert resp.status_code == 200
    assert "مهمة مُعيَّنة لدكتور بدون target_role".encode() in resp.data

    resp2 = logged_in_client.get("/team/tasks?role=worker")
    assert "مهمة مُعيَّنة لدكتور بدون target_role".encode() not in resp2.data


def test_invalid_role_query_param_falls_back_to_all(app, logged_in_client):
    t = Task(title="مهمة أي دور", task_type="custom", status="suggested")
    db.session.add(t)
    db.session.commit()

    resp = logged_in_client.get("/team/tasks?role=not_a_real_role")
    assert resp.status_code == 200
    assert "مهمة أي دور".encode() in resp.data
