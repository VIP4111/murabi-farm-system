"""بند إضافي 293 — طلبك "ابحث" بعد إغلاق حلقة بند 286-292. لقينا نفس
نمط فجوة السلالة (بند 291) بمكان ثانٍ: تبويبات فلترة المهام + قائمة
"الدور المستهدف" بفورم توزيع مهمة كانتا قائمة ثابتة بالكود
(worker/doctor/accountant بس) — أي مسمّى وظيفي مخصَّص ينشئه المالك من
الإعدادات (بند 267، "المزارع" مثلاً) ما كان يقدر يُستهدف بمهمة إطلاقاً."""
from app.extensions import db
from app.models import Role


def _add_custom_role(name="المزارع"):
    role = Role(name=name, display_name=name, is_system=False)
    db.session.add(role)
    db.session.commit()
    return role


def test_custom_role_appears_in_task_assign_target_role_dropdown(app, logged_in_client):
    _add_custom_role()
    resp = logged_in_client.get("/team/tasks/new")
    assert resp.status_code == 200
    assert "المزارع".encode() in resp.data


def test_custom_role_appears_in_tasks_list_filter_tabs(app, logged_in_client):
    _add_custom_role()
    resp = logged_in_client.get("/team/tasks")
    assert resp.status_code == 200
    assert "المزارع".encode() in resp.data


def test_owner_role_excluded_from_target_role_options(app, logged_in_client):
    resp = logged_in_client.get("/team/tasks/new")
    body = resp.data.decode()
    # "صاحب الحلال" (الاسم المعروض لدور owner) ما يفترض يظهر كخيار
    # "دور مستهدف" — نفس السلوك القديم المقصود.
    assert 'value="owner"' not in body


def test_filtering_tasks_by_custom_role_works(app, logged_in_client):
    from app.models import Task
    role = _add_custom_role()
    db.session.add(Task(title="مهمة للمزارع", task_type="custom", status="pending", target_role=role.name))
    db.session.add(Task(title="مهمة للعامل", task_type="custom", status="pending", target_role="worker"))
    db.session.commit()

    resp = logged_in_client.get(f"/team/tasks?role={role.name}")
    body = resp.data.decode()
    assert "مهمة للمزارع" in body
