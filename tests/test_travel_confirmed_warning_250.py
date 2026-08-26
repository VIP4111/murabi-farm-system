"""بند إضافي 250 — بعد نقد صريح: "لو عدّلت أو حذفت فترة سفر لشهر
راتبه متأكَّد أصلاً، ما فيه أي تنبيه". الراتب المؤكَّد Snapshot ثابت
عمداً (بند 242) وما يتغيَّر تلقائياً — بس تحذير يعلم المستخدم لو
احتاج يعدّله يدوياً."""
import re
from datetime import date

from app.extensions import db
from app.team import payroll_service
from app.models import Role, User, WorkerTravelPeriod


def _worker(phone):
    role = Role.query.filter_by(name="worker").first()
    u = User(name=f"عامل {phone}", phone=phone, role_id=role.id, language="ar", base_salary=1500)
    u.set_password("pass1234")
    db.session.add(u)
    db.session.commit()
    return u


def _csrf(html: str) -> str:
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def test_confirmed_payrolls_touched_by_period(app, owner):
    worker = _worker("0500050001")
    p = payroll_service.get_or_create_draft(user=worker, year=2026, month=3)
    payroll_service.save_draft(p, base_salary=1500, bonus_amount=0, deductions=[], recipient_name=None)
    payroll_service.confirm(p, actor=owner)

    touched = payroll_service.confirmed_payrolls_touched_by_period(worker.id, date(2026, 3, 10), date(2026, 3, 20))
    assert len(touched) == 1
    assert touched[0].id == p.id

    not_touched = payroll_service.confirmed_payrolls_touched_by_period(worker.id, date(2026, 4, 1), date(2026, 4, 10))
    assert not_touched == []


def test_add_period_warns_when_touching_confirmed_month(app, owner, logged_in_client):
    worker = _worker("0500050002")
    p = payroll_service.get_or_create_draft(user=worker, year=2026, month=3)
    payroll_service.save_draft(p, base_salary=1500, bonus_amount=0, deductions=[], recipient_name=None)
    payroll_service.confirm(p, actor=owner)

    resp = logged_in_client.get(f"/team/salaries/{worker.id}/travel-history")
    token = _csrf(resp.data.decode())
    resp2 = logged_in_client.post(f"/team/salaries/{worker.id}/travel-history/add", data={
        "csrf_token": token, "start_date": "2026-03-05", "end_date": "2026-03-10",
    }, follow_redirects=True)
    assert resp2.status_code == 200
    assert "راتب مؤكَّد بالفعل" in resp2.data.decode()


def test_add_period_no_warning_for_unconfirmed_month(app, logged_in_client):
    worker = _worker("0500050003")
    resp = logged_in_client.get(f"/team/salaries/{worker.id}/travel-history")
    token = _csrf(resp.data.decode())
    resp2 = logged_in_client.post(f"/team/salaries/{worker.id}/travel-history/add", data={
        "csrf_token": token, "start_date": "2026-03-05", "end_date": "2026-03-10",
    }, follow_redirects=True)
    assert resp2.status_code == 200
    assert "راتب مؤكَّد بالفعل" not in resp2.data.decode()


def test_delete_period_warns_when_touching_confirmed_month(app, owner, logged_in_client):
    worker = _worker("0500050004")
    period = WorkerTravelPeriod(user_id=worker.id, start_date=date(2026, 3, 5), end_date=date(2026, 3, 10))
    db.session.add(period)
    db.session.commit()

    p = payroll_service.get_or_create_draft(user=worker, year=2026, month=3)
    payroll_service.save_draft(p, base_salary=1500, bonus_amount=0, deductions=[], recipient_name=None)
    payroll_service.confirm(p, actor=owner)

    resp = logged_in_client.get(f"/team/salaries/{worker.id}/travel-history")
    token = _csrf(resp.data.decode())
    resp2 = logged_in_client.post(f"/team/travel-history/{period.id}/delete", data={
        "csrf_token": token,
    }, follow_redirects=True)
    assert resp2.status_code == 200
    assert "راتب مؤكَّد بالفعل" in resp2.data.decode()


def test_update_period_warns_when_new_range_touches_confirmed_month(app, owner, logged_in_client):
    worker = _worker("0500050005")
    period = WorkerTravelPeriod(user_id=worker.id, start_date=date(2026, 4, 5), end_date=date(2026, 4, 10))
    db.session.add(period)
    db.session.commit()

    p = payroll_service.get_or_create_draft(user=worker, year=2026, month=3)
    payroll_service.save_draft(p, base_salary=1500, bonus_amount=0, deductions=[], recipient_name=None)
    payroll_service.confirm(p, actor=owner)

    resp = logged_in_client.get(f"/team/salaries/{worker.id}/travel-history")
    token = _csrf(resp.data.decode())
    resp2 = logged_in_client.post(f"/team/travel-history/{period.id}/update", data={
        "csrf_token": token, "start_date": "2026-03-15", "end_date": "2026-03-20",
    }, follow_redirects=True)
    assert resp2.status_code == 200
    assert "راتب مؤكَّد بالفعل" in resp2.data.decode()
