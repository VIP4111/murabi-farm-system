"""بند إضافي 231 (تكملة) — تجاوز فترة السحب بصلاحية موثَّقة، حظيرة
نفاس منفصلة عن حظيرة العزل، وسجل تدقيق لإلغاء المهام عند البيع."""
from datetime import date, timedelta

from app.extensions import db
from app.core import cycle_engine, isolation_service
from app.health import health_service
from app.models import AuditLog, Task, Disease, Role, User
from tests.factories import make_animal, make_barn, make_pharmacy


def _force_stage_10(animal):
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


def _under_withdrawal_animal(animal_no, monkeypatch):
    animal = make_animal(animal_no=animal_no, price=500)
    cycle_engine.get_or_create_workflow(animal)
    monkeypatch.setattr(cycle_engine, "evaluate", _force_stage_10(animal))
    pharmacy = make_pharmacy(name="دواء تحريم " + animal_no, available_qty=10, withdrawal_days=10)
    health_service.record_vaccination(actor_user_id=1, animal_id=animal.id, vaccine_name="لقاح",
                                       date_=date.today(), pharmacy_id=pharmacy.id, quantity_used=1)
    return animal


# ---------- بند 1: تجاوز فترة السحب ----------

def test_withdrawal_override_with_reason_succeeds_and_logs(app, monkeypatch):
    animal = _under_withdrawal_animal("WD-OV-01", monkeypatch)
    cycle_engine.sell_animal(
        animal, sale_price=600, actor_user_id=1,
        withdrawal_override_reason="ذبح اضطراري بموافقة الطبيب",
    )
    assert animal.status == "sold"
    log = AuditLog.query.filter_by(action="animal.withdrawal_override").first()
    assert log is not None
    assert "ذبح اضطراري" in log.details


def test_withdrawal_still_blocked_without_reason(app, monkeypatch):
    animal = _under_withdrawal_animal("WD-OV-02", monkeypatch)
    try:
        cycle_engine.sell_animal(animal, sale_price=600, actor_user_id=1)
        assert False, "expected CycleExitBlocked"
    except cycle_engine.CycleExitBlocked:
        pass
    assert animal.status == "active"


def test_route_ignores_override_reason_without_permission(app, monkeypatch):
    animal = _under_withdrawal_animal("WD-OV-03", monkeypatch)
    role = Role.query.filter_by(name="worker").first()
    worker = User(name="عامل بلا صلاحية", phone="0500099099", role_id=role.id, language="ar")
    worker.set_password("pass1234")
    db.session.add(worker)
    db.session.commit()
    assert not worker.has_permission("sales.override_withdrawal")


# ---------- بند 4: سجل تدقيق لإلغاء المهام عند البيع ----------

def test_cancelled_tasks_on_sale_have_audit_log(app, monkeypatch):
    animal = _under_withdrawal_animal("WD-OV-04", monkeypatch)
    task = Task(title="مهمة مرتبطة", task_type="custom", status="pending", animal_id=animal.id)
    db.session.add(task)
    db.session.commit()

    cycle_engine.sell_animal(animal, sale_price=600, actor_user_id=1, withdrawal_override_reason="سبب")
    db.session.refresh(task)
    assert task.status == "cancelled"
    log = AuditLog.query.filter_by(action="task.auto_cancel_on_animal_exit", entity_id=task.id).first()
    assert log is not None


# ---------- بند 3: حظيرة النفاس منفصلة عن حظيرة العزل ----------

def test_birth_prefers_nefas_barn_over_isolation_barn(app):
    isolation_barn = make_barn(barn_no="ISO-01", barn_name="عزل الشراء", barn_type="عزل")
    nefas_barn = make_barn(barn_no="NEF-01", barn_name="نفاس الولادات", barn_type="نفاس")
    mother = make_animal(animal_no="MOM-NEF", gender="أنثى")
    newborn = make_animal(animal_no="KID-NEF", gender="ذكر")

    warning = isolation_service.start_isolation_plan(mother=mother, newborn=newborn, birth_date_=date.today())
    assert mother.barn_id == nefas_barn.id
    assert newborn.barn_id == nefas_barn.id
    assert warning is None


def test_birth_falls_back_to_isolation_barn_when_no_nefas(app):
    isolation_barn = make_barn(barn_no="ISO-02", barn_name="عزل فقط", barn_type="عزل")
    mother = make_animal(animal_no="MOM-FALLBACK", gender="أنثى")
    newborn = make_animal(animal_no="KID-FALLBACK", gender="ذكر")

    isolation_service.start_isolation_plan(mother=mother, newborn=newborn, birth_date_=date.today())
    assert mother.barn_id == isolation_barn.id
    assert newborn.barn_id == isolation_barn.id


def test_birth_warns_when_isolation_barn_has_sick_animal(app):
    barn = make_barn(barn_no="NEF-02", barn_name="نفاس فيه مرض", barn_type="نفاس")
    sick = make_animal(animal_no="SICK-01", barn_id=barn.id)
    db.session.add(Disease(animal_id=sick.id, status="active",
                            disease_name="اختبار", date=date.today()))
    db.session.commit()

    mother = make_animal(animal_no="MOM-WARN", gender="أنثى")
    newborn = make_animal(animal_no="KID-WARN", gender="ذكر")
    warning = isolation_service.start_isolation_plan(mother=mother, newborn=newborn, birth_date_=date.today())
    assert warning is not None
    assert "حالة مرضية مفتوحة" in warning
