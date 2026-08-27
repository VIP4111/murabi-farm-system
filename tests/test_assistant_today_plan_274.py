"""بند إضافي 274 — طلبك الصريح: "ارفع اكثر مثل ماذا علي فعله اليوم".
نية جديدة "ماذا أسوي اليوم؟" تجمع مهامك المفتوحة + أهم التنبيهات
العاجلة برد واحد مختصر، بدل ما تسأل سؤالين منفصلين (مهامي + التنبيهات)."""
from datetime import date

from app.assistant import nlu_service
from app.extensions import db
from app.models import Task, Role, User


def _worker(phone="0500074001"):
    role = Role.query.filter_by(name="worker").first()
    u = User(name=f"عامل {phone}", phone=phone, role_id=role.id, language="ar")
    u.set_password("pass1234")
    db.session.add(u)
    db.session.commit()
    return u


def test_no_tasks_no_alerts_reply(app, owner):
    result = nlu_service.answer(owner, "ماذا علي فعله اليوم")
    assert result["intent_code"] == "today_plan"
    assert "ما عندك مهام مفتوحة اليوم" in result["reply"]


def test_lists_open_tasks(app, owner):
    task = Task(title="سقاية الحظيرة أ", status="pending", assignee_id=owner.id, due_date=date.today())
    db.session.add(task)
    db.session.commit()
    result = nlu_service.answer(owner, "وش برنامجي اليوم")
    assert result["intent_code"] == "today_plan"
    assert "سقاية الحظيرة أ" in result["reply"]


def test_worker_without_animals_view_gets_tasks_only_no_error(app):
    worker = _worker()
    task = Task(title="تنظيف الحظيرة", status="pending", assignee_id=worker.id)
    db.session.add(task)
    db.session.commit()
    result = nlu_service.answer(worker, "شنو اسوي اليوم")
    assert result["intent_code"] == "today_plan"
    assert "تنظيف الحظيرة" in result["reply"]
    assert "تنبيه" not in result["reply"]


def test_this_intent_takes_priority_over_generic_tasks_question(app, owner):
    result = nlu_service.answer(owner, "ماذا اسوي اليوم")
    assert result["intent_code"] == "today_plan"
