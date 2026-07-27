"""اختبارات تحديث منطق الأتمتة ودورة عمل المهام والمخزون (بند إضافي 50):
حارس منع تكرار جرعة الطفيليات، حظر البيع الآلي أثناء فترة التحريم،
التفصيل الشامل للمهام، و"تأكيد التنفيذ"."""
from datetime import date, timedelta

import pytest

from app.extensions import db
from app.core import cycle_engine
from app.health import health_service
from app.models import FarmSettings, Task
from app.team import task_service as tsvc
from factories import make_animal, make_barn, make_pharmacy


# ---------- حارس منع تكرار جرعة الطفيليات (30 يوماً افتراضياً) ----------

def test_redose_guard_none_for_non_antiparasitic(app):
    animal = make_animal(animal_no="RD-01")
    pharmacy = make_pharmacy(name="مضاد حيوي", medicine_class="antibiotic")
    health_service.record_vaccination(actor_user_id=1, animal_id=animal.id, vaccine_name="جرعة",
                                       date_=date.today(), pharmacy_id=pharmacy.id, quantity_used=1)
    assert health_service.redose_guard_warning(animal_id=animal.id, pharmacy=pharmacy, redose_days=30) is None


def test_redose_guard_none_without_prior_dose(app):
    animal = make_animal(animal_no="RD-02")
    pharmacy = make_pharmacy(name="مضاد طفيليات", medicine_class="antiparasitic")
    assert health_service.redose_guard_warning(animal_id=animal.id, pharmacy=pharmacy, redose_days=30) is None


def test_redose_guard_warns_within_window(app):
    animal = make_animal(animal_no="RD-03")
    pharmacy = make_pharmacy(name="مضاد طفيليات", available_qty=10, medicine_class="antiparasitic")
    health_service.record_vaccination(actor_user_id=1, animal_id=animal.id, vaccine_name="جرعة أولى",
                                       date_=date.today() - timedelta(days=10), pharmacy_id=pharmacy.id,
                                       quantity_used=1)
    warning = health_service.redose_guard_warning(animal_id=animal.id, pharmacy=pharmacy, redose_days=30)
    assert warning is not None
    assert warning["days_since"] == 10


def test_redose_guard_none_after_window_passes(app):
    animal = make_animal(animal_no="RD-04")
    pharmacy = make_pharmacy(name="مضاد طفيليات", available_qty=10, medicine_class="antiparasitic")
    health_service.record_vaccination(actor_user_id=1, animal_id=animal.id, vaccine_name="جرعة أولى",
                                       date_=date.today() - timedelta(days=40), pharmacy_id=pharmacy.id,
                                       quantity_used=1)
    assert health_service.redose_guard_warning(animal_id=animal.id, pharmacy=pharmacy, redose_days=30) is None


def test_vaccination_route_blocks_redose_without_override(app, logged_in_client):
    animal = make_animal(animal_no="RD-05")
    pharmacy = make_pharmacy(name="مضاد طفيليات", available_qty=10, medicine_class="antiparasitic")
    health_service.record_vaccination(actor_user_id=1, animal_id=animal.id, vaccine_name="جرعة أولى",
                                       date_=date.today() - timedelta(days=5), pharmacy_id=pharmacy.id,
                                       quantity_used=1)
    before = _vacc_count()

    resp = logged_in_client.post("/health/vaccinations/new", data={
        "animal_id": str(animal.id), "vaccine_name": "جرعة ثانية",
        "date": date.today().isoformat(), "pharmacy_id": str(pharmacy.id), "quantity_used": "1",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert _vacc_count() == before, "لازم يُرفض بدون سبب تجاوز"


def test_vaccination_route_allows_redose_with_override_reason(app, logged_in_client):
    animal = make_animal(animal_no="RD-06")
    pharmacy = make_pharmacy(name="مضاد طفيليات", available_qty=10, medicine_class="antiparasitic")
    health_service.record_vaccination(actor_user_id=1, animal_id=animal.id, vaccine_name="جرعة أولى",
                                       date_=date.today() - timedelta(days=5), pharmacy_id=pharmacy.id,
                                       quantity_used=1)
    before = _vacc_count()

    resp = logged_in_client.post("/health/vaccinations/new", data={
        "animal_id": str(animal.id), "vaccine_name": "جرعة ثانية",
        "date": date.today().isoformat(), "pharmacy_id": str(pharmacy.id), "quantity_used": "1",
        "redose_override_reason": "إصابة مؤكدة مخبرياً بعد فحص برازي",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert _vacc_count() == before + 1
    from app.models import AuditLog
    assert AuditLog.query.filter_by(action="health.redose_override").count() == 1


def _vacc_count():
    from app.models import Vaccination
    return Vaccination.query.count()


# ---------- حظر البيع الآلي أثناء فترة التحريم ----------

def _force_stage_10(animal):
    """يحاكي حيواناً وصل فعلياً لمرحلة "قرار المصير" — بناء المسار
    الكامل للعشر مراحل يحتاج بيانات تكاثر/صحة كثيرة (نفس القيد الموثّق
    بـ`test_cycle_engine.py`)، فنحاكي evaluate() مباشرة عشان نختبر
    إضافة بند 50 (حظر التحريم) بمعزل عن منطق بوابات المراحل نفسه
    (مغطّى بملف ثاني أصلاً)."""
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


def test_sell_blocked_during_active_withdrawal(app, monkeypatch):
    animal = make_animal(animal_no="WD-01", price=500)
    cycle_engine.get_or_create_workflow(animal)
    monkeypatch.setattr(cycle_engine, "evaluate", _force_stage_10(animal))

    pharmacy = make_pharmacy(name="دواء تحريم", available_qty=10, withdrawal_days=10)
    health_service.record_vaccination(actor_user_id=1, animal_id=animal.id, vaccine_name="لقاح",
                                       date_=date.today(), pharmacy_id=pharmacy.id, quantity_used=1)

    with pytest.raises(cycle_engine.CycleExitBlocked) as exc:
        cycle_engine.sell_animal(animal, sale_price=600, actor_user_id=1)
    assert "تحريم" in str(exc.value)
    assert animal.status == "active"


def test_sell_allowed_after_withdrawal_expired(app, monkeypatch):
    animal = make_animal(animal_no="WD-02", price=500)
    cycle_engine.get_or_create_workflow(animal)
    monkeypatch.setattr(cycle_engine, "evaluate", _force_stage_10(animal))

    pharmacy = make_pharmacy(name="دواء تحريم منتهي", available_qty=10, withdrawal_days=10)
    old_date = date.today() - timedelta(days=20)
    health_service.record_vaccination(actor_user_id=1, animal_id=animal.id, vaccine_name="لقاح",
                                       date_=old_date, pharmacy_id=pharmacy.id, quantity_used=1)

    # يُرفع تلقائياً — بدون أي تحديث يدوي أو مهمة مجدولة (محسوب حياً)
    cycle_engine.sell_animal(animal, sale_price=600, actor_user_id=1)
    assert animal.status == "sold"


# ---------- التفصيل الشامل للمهام (batch/rich context) ----------

def test_batch_siblings_single_task_without_shared_source(app):
    barn = make_barn()
    task = tsvc.create_suggested_task(title="مهمة منفردة", task_type="custom", barn_id=barn.id)
    assert tsvc.batch_siblings(task) == [task]


def test_batch_siblings_groups_by_shared_source(app):
    barn = make_barn()
    a1 = make_animal(animal_no="B-01", barn_id=barn.id)
    a2 = make_animal(animal_no="B-02", barn_id=barn.id)
    t1 = tsvc.create_suggested_task(title="ت1", task_type="planned_treatment", barn_id=barn.id,
                                     animal_id=a1.id, source_type="BatchTreatmentPlan", source_id=100)
    t2 = tsvc.create_suggested_task(title="ت2", task_type="planned_treatment", barn_id=barn.id,
                                     animal_id=a2.id, source_type="BatchTreatmentPlan", source_id=100)
    siblings = tsvc.batch_siblings(t1)
    assert {s.id for s in siblings} == {t1.id, t2.id}


def test_task_rich_context_computes_stock_preview(app):
    barn = make_barn()
    a1 = make_animal(animal_no="B-03", barn_id=barn.id)
    a2 = make_animal(animal_no="B-04", barn_id=barn.id)
    pharmacy = make_pharmacy(name="دواء الدفعة", available_qty=20)

    t1 = tsvc.create_suggested_task(title="ت1", task_type="planned_treatment", barn_id=barn.id,
                                     animal_id=a1.id, source_type="BatchTreatmentPlan", source_id=200,
                                     notes="سبب الاختبار")
    t1.planned_pharmacy_id = pharmacy.id
    t1.planned_quantity = 3
    t2 = tsvc.create_suggested_task(title="ت2", task_type="planned_treatment", barn_id=barn.id,
                                     animal_id=a2.id, source_type="BatchTreatmentPlan", source_id=200)
    t2.planned_pharmacy_id = pharmacy.id
    t2.planned_quantity = 3
    db.session.commit()

    ctx = tsvc.task_rich_context(t1)
    assert ctx["head_count"] == 2
    assert ctx["total_quantity"] == 6
    assert ctx["stock_now"] == 20
    assert ctx["stock_after"] == 14
    assert ctx["stock_insufficient"] is False
    assert ctx["next_action"] is not None
    assert ctx["reason"] == "سبب الاختبار"


def test_task_rich_context_flags_insufficient_stock(app):
    barn = make_barn()
    animal = make_animal(animal_no="B-05", barn_id=barn.id)
    pharmacy = make_pharmacy(name="دواء نادر", available_qty=2)
    task = tsvc.create_suggested_task(title="ت", task_type="planned_treatment", barn_id=barn.id,
                                       animal_id=animal.id)
    task.planned_pharmacy_id = pharmacy.id
    task.planned_quantity = 5
    db.session.commit()

    ctx = tsvc.task_rich_context(task)
    assert ctx["stock_insufficient"] is True


# ---------- تأكيد التنفيذ (Confirm Execution) ----------

def test_complete_task_via_treatment_bypasses_assignee_check(app):
    """الفعل الحقيقي (تسجيل طبي بصلاحية health.manage) هو الحاسم، لا
    تطابق المكلَّف — الدكتور غالباً مو نفس العامل المكلَّف بالمهمة."""
    barn = make_barn()
    animal = make_animal(animal_no="CE-01", barn_id=barn.id)
    task = tsvc.create_suggested_task(title="مهمة", task_type="planned_treatment",
                                       barn_id=barn.id, animal_id=animal.id)
    assert task.assignee_id is None

    class _FakeActor:
        id = 999

    tsvc.complete_task_via_treatment(task, actor=_FakeActor())
    assert task.status == "done"
    assert task.completed_at is not None


def test_schedule_reweigh_followup_due_date_from_settings(app):
    barn = make_barn()
    animal = make_animal(animal_no="CE-02", barn_id=barn.id)
    fs = FarmSettings.get()
    fs.reweigh_followup_days = 14
    db.session.commit()

    task = tsvc.create_suggested_task(title="علاج", task_type="planned_treatment",
                                       barn_id=barn.id, animal_id=animal.id)

    class _FakeActor:
        id = 1

    followup = tsvc.schedule_reweigh_followup(task, actor=_FakeActor())
    assert followup is not None
    assert followup.due_date == date.today() + timedelta(days=14)
    assert followup.animal_id == animal.id
    assert followup.source_type == "TreatmentFollowUp"
    assert followup.source_id == task.id


def test_vaccination_route_with_task_id_completes_task_and_schedules_followup(app, logged_in_client):
    barn = make_barn()
    animal = make_animal(animal_no="CE-03", barn_id=barn.id)
    pharmacy = make_pharmacy(name="دواء تنفيذ", available_qty=10)
    task = tsvc.create_suggested_task(title="تنفيذ تطعيم مخطَّط", task_type="planned_treatment",
                                       barn_id=barn.id, animal_id=animal.id)
    task.planned_pharmacy_id = pharmacy.id
    task.planned_quantity = 2
    task.planned_treatment_kind = "vaccination"
    task.status = "pending"
    db.session.commit()

    resp = logged_in_client.post("/health/vaccinations/new", data={
        "animal_id": str(animal.id), "vaccine_name": "لقاح مخطَّط",
        "date": date.today().isoformat(), "pharmacy_id": str(pharmacy.id), "quantity_used": "2",
        "task_id": str(task.id),
    }, follow_redirects=True)
    assert resp.status_code == 200

    db.session.refresh(task)
    assert task.status == "done"
    assert pharmacy.available_qty == 8

    followup = Task.query.filter_by(source_type="TreatmentFollowUp", source_id=task.id).first()
    assert followup is not None
    assert followup.due_date == date.today() + timedelta(days=FarmSettings.get().reweigh_followup_days)


# ---------- خطة علاج جماعي (بند إضافي 50) ----------

def test_bulk_treatment_plan_creates_linked_suggested_tasks_without_deducting(app, logged_in_client):
    barn = make_barn()
    a1 = make_animal(animal_no="BP-01", barn_id=barn.id)
    a2 = make_animal(animal_no="BP-02", barn_id=barn.id)
    pharmacy = make_pharmacy(name="دواء دفعة", available_qty=50)

    resp = logged_in_client.post("/animals/bulk/apply/treatment-plan", data={
        "animal_ids": [str(a1.id), str(a2.id)],
        "pharmacy_id": str(pharmacy.id),
        "quantity_per_head": "2",
        "treatment_kind": "vaccination",
        "reason": "فحص دوري كشف انتشار طفيليات بالحظيرة",
        "due_date": date.today().isoformat(),
    }, follow_redirects=True)
    assert resp.status_code == 200

    # صفر خصم فعلي عند إنشاء الخطة — الشرط الأول بالكامل (بند إضافي 50)
    assert pharmacy.available_qty == 50

    tasks = Task.query.filter_by(source_type="BatchTreatmentPlan").all()
    assert len(tasks) == 2
    assert len({t.source_id for t in tasks}) == 1, "كل مهام الدفعة تشترك بنفس source_id"
    assert all(t.status == "suggested" for t in tasks)
    assert all(t.planned_pharmacy_id == pharmacy.id for t in tasks)
    assert all(t.planned_quantity == 2 for t in tasks)

# ملاحظة: اختبارات تتبّع تنفيذ العامل بدقة (بند إضافي 54) موجودة كاملة
# بملف مخصَّص `tests/test_task_worker_execution.py` — لا تُكرَّر هنا.
