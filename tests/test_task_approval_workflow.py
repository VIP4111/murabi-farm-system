"""اختبارات إعادة هيكلة تدفق اعتماد المهام (بند إضافي 70): تسميات جديدة
+ جدول "المهام المعتمدة" العام (كل مهمة معتمدة بالمزرعة، بغض النظر عن
المكلَّف بها — يختلف عن "مهامي" الخاصة بالمستخدم الحالي)."""
from app.extensions import db
from app.models import Task


def test_suggested_section_renamed(app, logged_in_client):
    resp = logged_in_client.get("/team/tasks")
    assert resp.status_code == 200
    assert "مهام مقترحة بانتظار الاعتماد".encode() in resp.data


def test_approve_button_renamed(app, logged_in_client):
    t = Task(title="مهمة اعتماد 70", task_type="custom", status="suggested")
    db.session.add(t)
    db.session.commit()
    resp = logged_in_client.get("/team/tasks")
    assert "اعتماد وإرسال".encode() in resp.data
    assert ">موافقة<".encode() not in resp.data


def test_approved_tasks_table_shows_all_pending_tasks_regardless_of_assignee(app, logged_in_client, worker):
    t = Task(title="مهمة معتمدة لعامل آخر", task_type="custom", status="pending",
             assignee_id=worker.id)
    db.session.add(t)
    db.session.commit()

    resp = logged_in_client.get("/team/tasks")
    assert resp.status_code == 200
    assert "جدول المهام المعتمدة".encode() in resp.data
    assert "مهمة معتمدة لعامل آخر".encode() in resp.data
    assert worker.name.encode() in resp.data


def test_approved_tasks_table_excludes_suggested_and_done(app, logged_in_client):
    suggested = Task(title="لسا مقترحة 70", task_type="custom", status="suggested")
    done = Task(title="منجزة فعلاً 70", task_type="custom", status="done")
    db.session.add_all([suggested, done])
    db.session.commit()

    resp = logged_in_client.get("/team/tasks")
    body = resp.data.decode("utf-8")
    approved_section = body[body.index("جدول المهام المعتمدة"):body.index("مهام وزّعتها")]
    assert "منجزة فعلاً 70" not in approved_section


def test_approving_suggested_task_moves_it_to_approved_table(app, logged_in_client):
    t = Task(title="مهمة تنتقل بعد الاعتماد", task_type="custom", status="suggested")
    db.session.add(t)
    db.session.commit()

    resp = logged_in_client.post(f"/team/tasks/{t.id}/approve", follow_redirects=True)
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    approved_section = body[body.index("جدول المهام المعتمدة"):body.index("مهام وزّعتها")]
    assert "مهمة تنتقل بعد الاعتماد" in approved_section
