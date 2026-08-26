"""بند إضافي 248 — بعد نقدك الصريح على شاشة "تقارير الرواتب" (ما فيها
إجمالي شهري لكل الفريق، بس تقرير عامل واحد). طلبت أطوّرها فأضفت بطاقة
"إجمالي رواتب الشهر" مستقلة عن اختيار العامل."""
from datetime import date

from app.extensions import db
from app.team import payroll_service
from app.models import Role, User


def _worker(phone, base_salary=1500):
    role = Role.query.filter_by(name="worker").first()
    u = User(name=f"عامل {phone}", phone=phone, role_id=role.id, language="ar", base_salary=base_salary)
    u.set_password("pass1234")
    db.session.add(u)
    db.session.commit()
    return u


def test_total_sums_only_confirmed_payrolls_for_selected_month(app, owner, logged_in_client):
    today = date.today()
    w1 = _worker("0500048001", base_salary=1000)
    w2 = _worker("0500048002", base_salary=2000)
    w3 = _worker("0500048003", base_salary=5000)

    for w, amount in [(w1, 1000), (w2, 2000)]:
        p = payroll_service.get_or_create_draft(user=w, year=today.year, month=today.month)
        payroll_service.save_draft(p, base_salary=amount, bonus_amount=0, deductions=[], recipient_name=None)
        payroll_service.confirm(p, actor=owner)

    # w3 يبقى مسودة — ما يُحسب بالإجمالي
    payroll_service.get_or_create_draft(user=w3, year=today.year, month=today.month)

    resp = logged_in_client.get(f"/team/payroll/reports?total_year={today.year}&total_month={today.month}")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "3000.00" in html
    assert w1.name in html
    assert w2.name in html


def test_total_defaults_to_current_month(app, owner, logged_in_client):
    today = date.today()
    w = _worker("0500048004", base_salary=1500)
    p = payroll_service.get_or_create_draft(user=w, year=today.year, month=today.month)
    payroll_service.save_draft(p, base_salary=1500, bonus_amount=0, deductions=[], recipient_name=None)
    payroll_service.confirm(p, actor=owner)

    resp = logged_in_client.get("/team/payroll/reports")
    assert resp.status_code == 200
    assert "1500.00" in resp.data.decode()


def test_total_zero_when_no_confirmed_payroll_that_month(app, logged_in_client):
    resp = logged_in_client.get("/team/payroll/reports?total_year=2020&total_month=1")
    assert resp.status_code == 200
    assert "0.00" in resp.data.decode()
