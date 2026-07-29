"""اختبارات ملاحظات إضافية بشاشة المهام (بند إضافي 72): تأجيل بضغطة
وحدة بدون خانة تاريخ، وشارة عنوان المهمة (أبيض + إطار) بدل رابط أزرق."""
from datetime import date, timedelta

from app.extensions import db
from app.models import Task


def test_postpone_without_date_field_defaults_to_plus_one_day(app, logged_in_client):
    t = Task(title="مهمة تأجيل 72", task_type="custom", status="suggested",
             due_date=date.today())
    db.session.add(t)
    db.session.commit()

    resp = logged_in_client.post(f"/team/tasks/{t.id}/postpone", data={}, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(t)
    assert t.due_date == date.today() + timedelta(days=1)


def test_postpone_with_no_prior_due_date_defaults_from_today(app, logged_in_client):
    t = Task(title="مهمة تأجيل 72-ب", task_type="custom", status="suggested", due_date=None)
    db.session.add(t)
    db.session.commit()

    resp = logged_in_client.post(f"/team/tasks/{t.id}/postpone", data={}, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(t)
    assert t.due_date == date.today() + timedelta(days=1)


def test_postpone_form_has_no_date_input(app, logged_in_client):
    t = Task(title="مهمة تأجيل 72-ج", task_type="custom", status="suggested")
    db.session.add(t)
    db.session.commit()

    resp = logged_in_client.get("/team/tasks")
    body = resp.data.decode("utf-8")
    idx = body.index(f'/team/tasks/{t.id}/postpone')
    form_slice = body[idx:idx + 200]
    assert 'type="date"' not in form_slice


def test_task_title_link_uses_badge_style_class(app, logged_in_client):
    resp = logged_in_client.get("/team/tasks")
    body = resp.data.decode("utf-8")
    assert "table.compact-table td a" in body
    assert "border:1.5px solid var(--primary2)" in body
