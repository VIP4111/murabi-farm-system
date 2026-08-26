"""بند إضافي 239 — موظف الشهر: اختيار تلقائي بناءً على محرك تقييم
الأداء الموضوعي (بند 229) على الشهر السابق كامل، بانتظار تأكيد صاحب
الحلال + تحديد مكافأة قبل ما تترحل حركة مالية فعلية."""
from datetime import date, datetime, timezone

from app.extensions import db
from app.team import employee_of_month_service as svc
from app.models import EmployeeOfMonth, Finance, Role, Task, User


def _worker(phone):
    role = Role.query.filter_by(name="worker").first()
    u = User(name=f"عامل {phone}", phone=phone, role_id=role.id, language="ar")
    u.set_password("pass1234")
    db.session.add(u)
    db.session.commit()
    return u


def _completed_task(user, when):
    t = Task(title="مهمة", task_type="custom", status="done", assignee_id=user.id)
    db.session.add(t)
    db.session.commit()
    t.completed_at = when
    db.session.commit()
    return t


def _mid_previous_month() -> datetime:
    today = date.today()
    first_of_this_month = today.replace(day=1)
    from datetime import timedelta
    last_of_prev = first_of_this_month - timedelta(days=1)
    return datetime.combine(last_of_prev.replace(day=min(15, last_of_prev.day)), datetime.min.time())


def test_selects_top_performer_from_previous_month(app):
    top = _worker("0500011001")
    low = _worker("0500011002")
    when = _mid_previous_month()
    for _ in range(5):
        _completed_task(top, when)
    _completed_task(low, when)
    from app.models import Task as TaskModel
    # يخلي الأداء فاشل جزئياً للعامل الثاني عشان نقطته أقل
    failing = Task(title="متعذّرة", task_type="custom", status="failed", assignee_id=low.id)
    db.session.add(failing)
    db.session.commit()
    failing.failed_at = when
    db.session.commit()

    record = svc.select_employee_of_month_if_needed()
    assert record is not None
    assert record.user_id == top.id
    assert record.status == "pending_confirmation"


def test_idempotent_no_duplicate_for_same_month(app):
    worker = _worker("0500011003")
    _completed_task(worker, _mid_previous_month())
    first = svc.select_employee_of_month_if_needed()
    second = svc.select_employee_of_month_if_needed()
    assert first is not None
    assert second is None
    assert EmployeeOfMonth.query.count() == 1


def test_no_selection_without_resolved_tasks(app):
    _worker("0500011004")
    record = svc.select_employee_of_month_if_needed()
    assert record is None
    assert EmployeeOfMonth.query.count() == 0


def test_confirm_creates_finance_record_and_updates_status(app, owner):
    worker = _worker("0500011005")
    _completed_task(worker, _mid_previous_month())
    record = svc.select_employee_of_month_if_needed()

    before = Finance.query.count()
    updated = svc.confirm(record, actor=owner, bonus_amount=500)

    assert updated.status == "confirmed"
    assert updated.bonus_amount == 500
    assert updated.confirmed_by_id == owner.id
    assert Finance.query.count() == before + 1
    fin = Finance.query.get(updated.finance_id)
    assert fin.operation_type == "expense"
    assert fin.amount == 500
    assert worker.name in fin.item


def test_pending_count_reflects_unconfirmed_records(app, owner):
    worker = _worker("0500011006")
    _completed_task(worker, _mid_previous_month())
    record = svc.select_employee_of_month_if_needed()
    assert svc.pending_count() == 1
    svc.confirm(record, actor=owner, bonus_amount=100)
    assert svc.pending_count() == 0


def test_confirm_route_requires_owner_role(app, client):
    role = Role.query.filter_by(name="doctor").first()
    doctor = User(name="دكتور", phone="0500011007", role_id=role.id, language="ar")
    doctor.set_password("pass1234")
    db.session.add(doctor)
    db.session.commit()
    client.post("/login", data={"phone": doctor.phone, "password": "pass1234"})

    resp = client.get("/team/employee-of-month")
    assert resp.status_code == 403
