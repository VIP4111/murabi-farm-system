"""بند إضافي 247 — طلبك الصريح: "النظام يعتمد رواتب العامل من تاريخ
وصوله الى تاريخ اخر شهر... كل شهر، دايماً حسب أيام الحضور الفعلية...
اضف زر سفر اذا كان مسافر يتسجل مسافر بدون راتب... الراتب يتقسم على
أيام الشهر". راتب متناسب حسب تاريخ الوصول للسعودية + فترات سفر."""
from datetime import date

from app.extensions import db
from app.team import payroll_service
from app.models import Role, User


def _worker(phone, base_salary=3000, arrival=None):
    role = Role.query.filter_by(name="worker").first()
    u = User(name=f"عامل {phone}", phone=phone, role_id=role.id, language="ar",
             base_salary=base_salary, saudi_arrival_date=arrival)
    u.set_password("pass1234")
    db.session.add(u)
    db.session.commit()
    return u


def test_no_arrival_date_means_full_month_no_proration(app):
    worker = _worker("0500047001")  # 30 يوم بسبتمبر
    present, total = payroll_service.present_days_in_month(worker, year=2026, month=9)
    assert present == total == 30
    assert payroll_service.prorated_salary(worker, year=2026, month=9) == 3000


def test_arrival_mid_month_prorates_that_month_only(app):
    worker = _worker("0500047002", base_salary=3000, arrival=date(2026, 9, 21))  # سبتمبر 30 يوم
    present, total = payroll_service.present_days_in_month(worker, year=2026, month=9)
    assert (present, total) == (10, 30)  # 21 لين 30 = 10 أيام
    assert payroll_service.prorated_salary(worker, year=2026, month=9) == 1000.0

    # الشهر التالي كامل (بعد الوصول)، ما فيه تناسب
    present2, total2 = payroll_service.present_days_in_month(worker, year=2026, month=10)
    assert present2 == total2 == 31
    assert payroll_service.prorated_salary(worker, year=2026, month=10) == 3000


def test_arrival_after_month_end_means_zero_days(app):
    worker = _worker("0500047003", arrival=date(2026, 10, 5))
    present, total = payroll_service.present_days_in_month(worker, year=2026, month=9)
    assert present == 0
    assert payroll_service.prorated_salary(worker, year=2026, month=9) == 0.0


def test_travel_period_reduces_days_that_month(app):
    worker = _worker("0500047004", base_salary=3000)  # سبتمبر 30 يوم
    from app.models import WorkerTravelPeriod
    db.session.add(WorkerTravelPeriod(user_id=worker.id, start_date=date(2026, 9, 10), end_date=date(2026, 9, 19)))
    db.session.commit()

    present, total = payroll_service.present_days_in_month(worker, year=2026, month=9)
    assert (present, total) == (20, 30)  # 10 أيام سفر مستبعدة
    assert payroll_service.prorated_salary(worker, year=2026, month=9) == 2000.0


def test_open_travel_period_capped_at_month_end(app):
    worker = _worker("0500047005", base_salary=3000)
    from app.models import WorkerTravelPeriod
    db.session.add(WorkerTravelPeriod(user_id=worker.id, start_date=date(2026, 9, 25), end_date=None))
    db.session.commit()

    present, total = payroll_service.present_days_in_month(worker, year=2026, month=9)
    assert (present, total) == (24, 30)  # 25-30 = 6 أيام مستبعدة


def test_travel_toggle_start_then_end(app):
    worker = _worker("0500047006")
    assert payroll_service.is_traveling(worker) is False
    payroll_service.start_travel(worker)
    assert payroll_service.is_traveling(worker) is True
    payroll_service.end_travel(worker)
    assert payroll_service.is_traveling(worker) is False


def test_draft_creation_uses_prorated_salary(app):
    worker = _worker("0500047007", base_salary=3000, arrival=date(2026, 9, 21))
    payroll = payroll_service.get_or_create_draft(user=worker, year=2026, month=9)
    assert payroll.base_salary == 1000.0


def test_salaries_list_route_shows_travel_badge(app, logged_in_client):
    worker = _worker("0500047008")
    payroll_service.start_travel(worker)
    resp = logged_in_client.get("/team/salaries")
    assert resp.status_code == 200
    assert "مسافر حالياً" in resp.data.decode()


def test_travel_toggle_route(app, logged_in_client):
    worker = _worker("0500047009")
    resp = logged_in_client.post(f"/team/salaries/{worker.id}/travel/toggle", follow_redirects=True)
    assert resp.status_code == 200
    assert payroll_service.is_traveling(worker) is True

    resp2 = logged_in_client.post(f"/team/salaries/{worker.id}/travel/toggle", follow_redirects=True)
    assert resp2.status_code == 200
    assert payroll_service.is_traveling(worker) is False


def test_salary_update_saves_arrival_date(app, logged_in_client):
    worker = _worker("0500047010")
    resp = logged_in_client.get("/team/salaries")
    import re
    token = re.search(r'name="csrf_token" value="([^"]+)"', resp.data.decode()).group(1)
    logged_in_client.post(f"/team/salaries/{worker.id}/update", data={
        "csrf_token": token, "base_salary": "3000", "saudi_arrival_date": "2026-09-21",
    }, follow_redirects=True)
    db.session.refresh(worker)
    assert worker.saudi_arrival_date == date(2026, 9, 21)
