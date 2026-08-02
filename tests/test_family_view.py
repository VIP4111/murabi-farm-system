"""بند إضافي 106 — شاشة متابعة مبسّطة لمستخدم مسنّ (طلب المالك تحديداً
لوالده): تقدّم كل عامل اليوم + ملاحظاته، ومخزون العلف/الصيدلية — عرض
بس، بدون أي تعديل، خط كبير ووضع ليلي."""
from datetime import date, timedelta

from app.extensions import db
from app.models import Task
from factories import make_animal, make_feed, make_pharmacy


def test_worker_with_open_task_appears(app, logged_in_client, worker):
    t = Task(title="مهمة مفتوحة اختبار", task_type="custom", status="pending",
              assignee_id=worker.id, due_date=date.today())
    db.session.add(t)
    db.session.commit()

    resp = logged_in_client.get("/family-view")
    body = resp.data.decode()
    assert worker.name in body
    assert "مهمة مفتوحة اختبار" in body
    assert "باقي" in body


def test_worker_completed_today_shows_note(app, logged_in_client, worker):
    t = Task(title="مهمة منجزة اختبار", task_type="custom", status="done",
              assignee_id=worker.id, completed_at=date.today(), completion_note="خلصت زي ما تبي")
    db.session.add(t)
    db.session.commit()

    resp = logged_in_client.get("/family-view")
    body = resp.data.decode()
    assert "مهمة منجزة اختبار" in body
    assert "خلصت زي ما تبي" in body


def test_worker_with_only_old_done_task_not_shown(app, logged_in_client, worker):
    t = Task(title="مهمة قديمة اختبار", task_type="custom", status="done",
              assignee_id=worker.id, completed_at=date.today() - timedelta(days=5))
    db.session.add(t)
    db.session.commit()

    resp = logged_in_client.get("/family-view")
    body = resp.data.decode()
    assert worker.name not in body


def test_feed_and_pharmacy_stock_shown(app, logged_in_client):
    make_feed(name="علف اختبار العرض", available_qty=42)
    make_pharmacy(name="دواء اختبار العرض", available_qty=7)

    resp = logged_in_client.get("/family-view")
    body = resp.data.decode()
    assert "علف اختبار العرض" in body
    assert "42" in body
    assert "دواء اختبار العرض" in body
