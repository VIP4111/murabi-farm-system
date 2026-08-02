"""بند إضافي 98 — إلغاء المهام المفتوحة تلقائياً عند بيع/نفوق/حذف رأس.
قبل هذا البند، مهام (تحصين، رش، خطوة بروتوكول علاج...) كانت تبقى معلَّقة
تشير لرأس مو موجود فعلياً."""
from datetime import date

from app.extensions import db
from app.core import cycle_engine
from app.models import Task
from factories import make_animal, make_barn


def _open_task(animal, task_type="custom", title="مهمة اختبار"):
    t = Task(title=title, task_type=task_type, status="pending", animal_id=animal.id, due_date=date.today())
    db.session.add(t)
    db.session.commit()
    return t


def _force_stage_10(animal):
    # sell_animal/delete_animal يتطلبان وصول الحيوان لمرحلة "قرار المصير"
    # (10) أولاً — نفس التزييف المستخدم بـtest_task_automation.py.
    def _fake_evaluate(a):
        wf = a.workflow
        wf.current_stage = 10
        wf.stage_name = "قرار المصير"
        wf.status = "complete"
        return {
            "route": wf.route, "allowed_stage": 10, "completed_through": 10,
            "first_blocked_stage": None, "cycle_status": "complete",
            "missing_items": None, "out_of_order_count": 0,
        }
    return _fake_evaluate


def test_sell_animal_cancels_open_tasks(app, monkeypatch):
    animal = make_animal(animal_no="SELL-01", price=500)
    cycle_engine.get_or_create_workflow(animal)
    monkeypatch.setattr(cycle_engine, "evaluate", _force_stage_10(animal))
    t1 = _open_task(animal, task_type="vaccination_due")
    t2 = _open_task(animal, task_type="protocol_step")

    cycle_engine.sell_animal(animal, sale_price=600, actor_user_id=1)

    db.session.refresh(t1)
    db.session.refresh(t2)
    assert t1.status == "cancelled"
    assert t2.status == "cancelled"
    assert "انباع" in t1.notes


def test_mark_animal_dead_cancels_open_tasks(app):
    animal = make_animal(animal_no="DEAD-01", price=500)
    cycle_engine.get_or_create_workflow(animal)
    t1 = _open_task(animal)

    cycle_engine.mark_animal_dead(animal, actor_user_id=1)

    db.session.refresh(t1)
    assert t1.status == "cancelled"
    assert "نفق" in t1.notes


def test_delete_animal_cancels_open_tasks(app, monkeypatch):
    animal = make_animal(animal_no="DEL-01")
    cycle_engine.get_or_create_workflow(animal)
    monkeypatch.setattr(cycle_engine, "evaluate", _force_stage_10(animal))
    t1 = _open_task(animal)

    cycle_engine.delete_animal(animal, actor_user_id=1, force=True)

    db.session.refresh(t1)
    assert t1.status == "cancelled"


def test_already_done_task_not_touched(app, monkeypatch):
    animal = make_animal(animal_no="SELL-02", price=500)
    cycle_engine.get_or_create_workflow(animal)
    monkeypatch.setattr(cycle_engine, "evaluate", _force_stage_10(animal))
    done_task = _open_task(animal)
    done_task.status = "done"
    done_task.completion_note = "already finished"
    db.session.commit()

    cycle_engine.sell_animal(animal, sale_price=600, actor_user_id=1)

    db.session.refresh(done_task)
    assert done_task.status == "done"
    assert done_task.notes is None


def test_task_for_other_animal_not_touched(app, monkeypatch):
    animal = make_animal(animal_no="SELL-03", price=500)
    other = make_animal(animal_no="OTHER-01")
    cycle_engine.get_or_create_workflow(animal)
    monkeypatch.setattr(cycle_engine, "evaluate", _force_stage_10(animal))
    other_task = _open_task(other)

    cycle_engine.sell_animal(animal, sale_price=600, actor_user_id=1)

    db.session.refresh(other_task)
    assert other_task.status == "pending"
