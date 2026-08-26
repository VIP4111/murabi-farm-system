"""بند إضافي 240 — وصل استلام مكافأة موظف الشهر لشهر واحد (بعد
التأكيد الفعلي)، مع اسم مستلم حوالة اختياري."""
from datetime import date, datetime, timedelta

from app.extensions import db
from app.team import employee_of_month_service as svc
from app.models import EmployeeOfMonth, FarmSettings, Role, Task, User


def _worker(phone):
    role = Role.query.filter_by(name="worker").first()
    u = User(name=f"عامل {phone}", phone=phone, role_id=role.id, language="ar")
    u.set_password("pass1234")
    db.session.add(u)
    db.session.commit()
    return u


def _mid_previous_month() -> datetime:
    today = date.today()
    first_of_this_month = today.replace(day=1)
    last_of_prev = first_of_this_month - timedelta(days=1)
    return datetime.combine(last_of_prev.replace(day=min(15, last_of_prev.day)), datetime.min.time())


def _confirmed_record(owner, recipient_name=None):
    worker = _worker("0500022001" if recipient_name is None else "0500022002")
    t = Task(title="مهمة", task_type="custom", status="done", assignee_id=worker.id)
    db.session.add(t)
    db.session.commit()
    t.completed_at = _mid_previous_month()
    db.session.commit()
    record = svc.select_employee_of_month_if_needed()
    return svc.confirm(record, actor=owner, bonus_amount=750, recipient_name=recipient_name)


def test_confirm_stores_recipient_name(app, owner):
    record = _confirmed_record(owner, recipient_name="أخو العامل")
    assert record.recipient_name == "أخو العامل"


def test_confirm_without_recipient_name_leaves_it_none(app, owner):
    record = _confirmed_record(owner, recipient_name=None)
    assert record.recipient_name is None


def test_receipt_pdf_builds_successfully(app, owner):
    record = _confirmed_record(owner, recipient_name="والد العامل")
    from app.reports.export_service import build_employee_of_month_receipt_pdf
    buf = build_employee_of_month_receipt_pdf(record, FarmSettings.get())
    data = buf.getvalue()
    assert data[:4] == b"%PDF"
    assert len(data) > 1000


def test_receipt_route_requires_confirmed_status(app, logged_in_client, owner):
    worker = _worker("0500022003")
    t = Task(title="مهمة", task_type="custom", status="done", assignee_id=worker.id)
    db.session.add(t)
    db.session.commit()
    t.completed_at = _mid_previous_month()
    db.session.commit()
    record = svc.select_employee_of_month_if_needed()

    resp = logged_in_client.get(f"/team/employee-of-month/{record.id}/receipt", follow_redirects=True)
    assert resp.status_code == 200
    assert "لسا ما تأكَّد" in resp.data.decode()


def test_receipt_route_returns_pdf_after_confirmation(app, logged_in_client, owner):
    record = _confirmed_record(owner, recipient_name="أخو العامل")
    resp = logged_in_client.get(f"/team/employee-of-month/{record.id}/receipt")
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"


def test_receipt_route_forbidden_for_non_owner(app, client):
    role = Role.query.filter_by(name="doctor").first()
    doctor = User(name="دكتور", phone="0500022004", role_id=role.id, language="ar")
    doctor.set_password("pass1234")
    db.session.add(doctor)
    db.session.commit()
    client.post("/login", data={"phone": doctor.phone, "password": "pass1234"})
    resp = client.get("/team/employee-of-month/1/receipt")
    assert resp.status_code == 403
