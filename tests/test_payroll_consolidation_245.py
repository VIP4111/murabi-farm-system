"""بند إضافي 245 — دمج "موظف الشهر" (بند 239-240) داخل نظام الرواتب
العام (بند 242) بدل نظامين متوازيين يسويان نفس الشيء تقريباً (حساب
مبلغ → ترحيل مالية → PDF → تأكيد صاحب الحلال). التنقية جات بعد طلب
المستخدم الصريح للنقد الصريح، وموافقته "ابدا خليني اشوفك ونت تتفنن"."""
from datetime import date, datetime, timezone

from app.extensions import db
from app.team import payroll_service
from app.models import Payroll, Role, User, Task


def _worker(phone, base_salary=1500):
    role = Role.query.filter_by(name="worker").first()
    u = User(name=f"عامل {phone}", phone=phone, role_id=role.id, language="ar", base_salary=base_salary)
    u.set_password("pass1234")
    db.session.add(u)
    db.session.commit()
    return u


def _completed_task(worker, when):
    t = Task(title="مهمة", assignee_id=worker.id, status="done", completed_at=when, due_date=when.date())
    db.session.add(t)
    db.session.commit()
    return t


def test_employee_of_month_routes_removed(logged_in_client):
    for path in ("/team/employee-of-month", "/team/employee-of-month/1/confirm", "/team/employee-of-month/1/receipt"):
        resp = logged_in_client.get(path)
        assert resp.status_code == 404


def test_top_performer_for_month_uses_live_performance_calc(app):
    worker = _worker("0500045001")
    last_month_day = date(2026, 7, 15)
    _completed_task(worker, datetime(2026, 7, 15, 10, 0, tzinfo=timezone.utc))

    top = payroll_service.top_performer_for_month(year=2026, month=7)
    assert top is not None
    assert top["user"].id == worker.id


def test_top_performer_none_when_no_resolved_tasks(app):
    _worker("0500045002")
    top = payroll_service.top_performer_for_month(year=2026, month=7)
    assert top is None


def test_prepare_route_shows_banner_only_for_top_performer_and_only_while_draft(app, logged_in_client, owner):
    worker = _worker("0500045003")
    _completed_task(worker, datetime(2026, 7, 15, 10, 0, tzinfo=timezone.utc))

    resp = logged_in_client.get(f"/team/payroll/{worker.id}/prepare?year=2026&month=8")
    assert resp.status_code == 200
    assert "أعلى نقطة أداء الشهر الماضي" in resp.data.decode()

    payroll = Payroll.query.filter_by(user_id=worker.id, year=2026, month=8).first()
    payroll_service.save_draft(payroll, base_salary=1500, bonus_amount=0, deductions=[], recipient_name=None)
    payroll_service.confirm(payroll, actor=owner)

    resp2 = logged_in_client.get(f"/team/payroll/{worker.id}/prepare?year=2026&month=8")
    assert "أعلى نقطة أداء الشهر الماضي" not in resp2.data.decode()


def test_prepare_route_no_banner_for_non_top_performer(app, logged_in_client, owner):
    worker = _worker("0500045004")
    other = _worker("0500045005")
    _completed_task(other, datetime(2026, 7, 15, 10, 0, tzinfo=timezone.utc))

    resp = logged_in_client.get(f"/team/payroll/{worker.id}/prepare?year=2026&month=8")
    assert "أعلى نقطة أداء الشهر الماضي" not in resp.data.decode()


def test_upload_receipt_route_get_renders_dedicated_page(app, logged_in_client, owner):
    worker = _worker("0500045006")
    today = date.today()
    payroll = payroll_service.get_or_create_draft(user=worker, year=today.year, month=today.month)
    payroll_service.save_draft(payroll, base_salary=1500, bonus_amount=0, deductions=[], recipient_name=None)
    payroll_service.confirm(payroll, actor=owner)

    resp = logged_in_client.get(f"/team/payroll/{payroll.id}/upload-receipt")
    assert resp.status_code == 200
    assert "الوصل الموقَّع" in resp.data.decode()


def test_upload_receipt_route_rejects_draft_payroll(app, logged_in_client, owner):
    worker = _worker("0500045007")
    today = date.today()
    payroll = payroll_service.get_or_create_draft(user=worker, year=today.year, month=today.month)

    resp = logged_in_client.get(f"/team/payroll/{payroll.id}/upload-receipt", follow_redirects=True)
    assert resp.status_code == 200
    assert "لازم يتأكَّد الراتب" in resp.data.decode()


def test_salaries_list_renamed_heading(app, logged_in_client):
    resp = logged_in_client.get("/team/salaries")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "إعداد الرواتب" in html
    assert "رواتب الشهر" in html
