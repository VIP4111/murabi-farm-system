"""بند إضافي 106 (أساس) + بند إضافي 109 (توسعة) — شاشة متابعة مبسّطة
لمستخدم مسنّ. المهام صارت مبوَّبة حسب الدور (صاحب الحلال/الطبيب/العامل)
بدل حسب كل عامل لحاله، والمخزون صار 3 أقسام (علف/صيدلية/معدات) بمعدل
استهلاك يوم/شهر، مع أزرار تأجيل/إلغاء فعلية للمهام المفتوحة."""
from datetime import date, datetime, timedelta, timezone

from app.extensions import db
from app.models import Task
from factories import make_feed, make_pharmacy, make_equipment


def test_worker_open_task_appears_under_worker_role(app, logged_in_client, worker):
    t = Task(title="مهمة مفتوحة اختبار", task_type="custom", status="pending",
              assignee_id=worker.id, due_date=date.today())
    db.session.add(t)
    db.session.commit()

    resp = logged_in_client.get("/family-view")
    body = resp.data.decode()
    assert "مهمة مفتوحة اختبار" in body
    assert "باقي" in body
    assert "تأجيل" in body
    assert "إلغاء" in body


def test_worker_completed_today_shows_lock_and_note(app, logged_in_client, worker):
    t = Task(title="مهمة منجزة اختبار", task_type="custom", status="done",
              assignee_id=worker.id, completed_at=date.today(), completion_note="خلصت زي ما تبي")
    db.session.add(t)
    db.session.commit()

    resp = logged_in_client.get("/family-view")
    body = resp.data.decode()
    assert "مهمة منجزة اختبار" in body
    assert "خلصت زي ما تبي" in body
    assert "قفل المهمة" in body


def test_completed_at_utc_near_local_midnight_still_shown_today(app, logged_in_client, worker):
    """completed_at يُخزَّن UTC (راجع _now() بـ app/team/task_service.py) بينما
    "اليوم" هنا date.today() محلي — بخادم بتوقيت أمام UTC (هذا الجهاز +3)،
    أول ساعات بعد منتصف الليل المحلي كانت func.date(completed_at) == today
    القديمة تفوّت المهمة لأن تاريخ UTC الخام لسه "أمس". يتحقق من الإصلاح
    باستخدام وقت UTC حقيقي حالي، بدون أي محاكاة للساعة."""
    t = Task(title="مهمة إنجاز الآن اختبار", task_type="custom", status="done",
              assignee_id=worker.id, completed_at=datetime.now(timezone.utc))
    db.session.add(t)
    db.session.commit()

    resp = logged_in_client.get("/family-view")
    assert "مهمة إنجاز الآن اختبار" in resp.data.decode()


def test_old_done_task_not_shown(app, logged_in_client, worker):
    t = Task(title="مهمة قديمة اختبار", task_type="custom", status="done",
              assignee_id=worker.id, completed_at=date.today() - timedelta(days=5))
    db.session.add(t)
    db.session.commit()

    resp = logged_in_client.get("/family-view")
    assert "مهمة قديمة اختبار" not in resp.data.decode()


def test_unassigned_role_matching_task_appears(app, logged_in_client):
    t = Task(title="مهمة عامة اختبار", task_type="daily_husbandry", status="pending",
              due_date=date.today(), target_role="worker")
    db.session.add(t)
    db.session.commit()

    resp = logged_in_client.get("/family-view")
    assert "مهمة عامة اختبار" in resp.data.decode()


def test_feed_pharmacy_equipment_stock_shown_with_stats(app, logged_in_client):
    make_feed(name="علف اختبار العرض", available_qty=42)
    make_pharmacy(name="دواء اختبار العرض", available_qty=7)
    make_equipment(name="أداة اختبار العرض", available_qty=3)

    resp = logged_in_client.get("/family-view")
    body = resp.data.decode()
    assert "علف اختبار العرض" in body
    assert "42" in body
    assert "دواء اختبار العرض" in body
    assert "أداة اختبار العرض" in body
    assert "المستهلك اليوم" in body
    assert "المصروف اليوم" in body


def test_postpone_active_route_moves_due_date(app, logged_in_client, worker):
    t = Task(title="مهمة تأجيل اختبار", task_type="custom", status="pending",
              assignee_id=worker.id, due_date=date.today())
    db.session.add(t)
    db.session.commit()

    resp = logged_in_client.post(f"/team/tasks/{t.id}/postpone-active")
    assert resp.status_code == 302
    db.session.refresh(t)
    assert t.due_date == date.today() + timedelta(days=1)


def test_cancel_active_route_sets_cancelled(app, logged_in_client, worker):
    t = Task(title="مهمة إلغاء اختبار", task_type="custom", status="pending",
              assignee_id=worker.id, due_date=date.today())
    db.session.add(t)
    db.session.commit()

    resp = logged_in_client.post(f"/team/tasks/{t.id}/cancel-active")
    assert resp.status_code == 302
    db.session.refresh(t)
    assert t.status == "cancelled"


def test_postpone_active_denied_without_permission(app, client, worker):
    t = Task(title="مهمة صلاحية اختبار", task_type="custom", status="pending",
              assignee_id=worker.id, due_date=date.today())
    db.session.add(t)
    db.session.commit()

    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    client.post(f"/team/tasks/{t.id}/postpone-active")
    db.session.refresh(t)
    assert t.due_date == date.today()  # ما تغيّر — العامل ماله صلاحية tasks.assign_any
