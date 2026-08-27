"""بند إضافي 266 — إكمال المسح المنهجي (بند 252/258/262/263/264/265):
قسم "الفريق والمهام" كان أكبر فجوة متبقية — بس 9 من 49 راوت مسجَّلة
بـ_team_endpoints. راجعت الجانب المالي أيضاً — كل حقول التكلفة بهذا
القسم مقصورة على الرواتب، اللي راجعناها بعمق أصلاً (بند 245-250)،
فما فيه فجوة جديدة هنا."""
from app.extensions import db
from factories import make_animal


def _drawer_open(html: str) -> bool:
    idx = html.find(">الفريق<")
    assert idx != -1
    details_idx = html.rfind("<details", 0, idx)
    return " open" in html[details_idx:idx]


def test_team_drawer_stays_open_on_members_new(app, logged_in_client):
    resp = logged_in_client.get("/team/members/new")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_team_drawer_stays_open_on_members_edit(app, logged_in_client, owner):
    resp = logged_in_client.get(f"/team/members/{owner.id}/edit")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_team_drawer_stays_open_on_reports_new(app, logged_in_client):
    resp = logged_in_client.get("/team/reports/new")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_team_drawer_stays_open_on_report_types_new(app, logged_in_client):
    resp = logged_in_client.get("/team/reports/types/new")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_team_drawer_stays_open_on_daily_templates_list(app, logged_in_client):
    resp = logged_in_client.get("/team/tasks/daily-templates")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_team_drawer_stays_open_on_tasks_new(app, logged_in_client):
    resp = logged_in_client.get("/team/tasks/new")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_team_drawer_stays_open_on_task_detail(app, logged_in_client):
    from app.models import Task
    task = Task(title="مهمة اختبار", status="pending")
    db.session.add(task)
    db.session.commit()
    resp = logged_in_client.get(f"/team/tasks/{task.id}")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_team_drawer_stays_open_on_worker_quick_report(app, logged_in_client):
    resp = logged_in_client.get("/team/worker/report/health")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())
