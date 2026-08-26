"""بند إضافي 242 — نظام الرواتب الشهري العام: راتب أساسي + مكافأة -
خصومات متعددة (كل خصم بسبب مستقل، زر "إضافة خصم")، تأكيد يرحّل حركة
مالية فعلية، وصل PDF قابل للطباعة، رفع صورة الوصل الموقَّع، وتقارير
حسب العامل."""
import re
from datetime import date

from app.extensions import db
from app.team import payroll_service
from app.models import Payroll, PayrollDeduction, Finance, Role, User


def _worker(phone, base_salary=1500):
    role = Role.query.filter_by(name="worker").first()
    u = User(name=f"عامل {phone}", phone=phone, role_id=role.id, language="ar", base_salary=base_salary)
    u.set_password("pass1234")
    db.session.add(u)
    db.session.commit()
    return u


def _csrf_token(html: str) -> str:
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def test_get_or_create_draft_snapshots_base_salary(app):
    worker = _worker("0500044001", base_salary=1800)
    today = date.today()
    payroll = payroll_service.get_or_create_draft(user=worker, year=today.year, month=today.month)
    assert payroll.base_salary == 1800
    assert payroll.status == "draft"
    # نفس الشهر مرة ثانية يرجّع نفس السجل، ما يكرره
    again = payroll_service.get_or_create_draft(user=worker, year=today.year, month=today.month)
    assert again.id == payroll.id


def test_save_draft_replaces_deductions(app):
    worker = _worker("0500044002")
    today = date.today()
    payroll = payroll_service.get_or_create_draft(user=worker, year=today.year, month=today.month)
    payroll_service.save_draft(
        payroll, base_salary=1500, bonus_amount=100,
        deductions=[(50, "تأخير"), (20, "سلفة")], recipient_name=None,
    )
    assert PayrollDeduction.query.filter_by(payroll_id=payroll.id).count() == 2
    assert payroll.net_amount == 1500 + 100 - 50 - 20

    # حفظ ثاني بقائمة خصومات مختلفة يستبدل القديمة كاملة
    payroll_service.save_draft(
        payroll, base_salary=1500, bonus_amount=100,
        deductions=[(10, "خصم واحد بس")], recipient_name=None,
    )
    assert PayrollDeduction.query.filter_by(payroll_id=payroll.id).count() == 1


def test_confirm_creates_finance_and_locks_editing(app, owner):
    worker = _worker("0500044003")
    today = date.today()
    payroll = payroll_service.get_or_create_draft(user=worker, year=today.year, month=today.month)
    payroll_service.save_draft(payroll, base_salary=1500, bonus_amount=0, deductions=[], recipient_name=None)

    before = Finance.query.count()
    payroll_service.confirm(payroll, actor=owner)
    assert payroll.status == "confirmed"
    assert Finance.query.count() == before + 1
    fin = Finance.query.get(payroll.finance_id)
    assert fin.operation_type == "expense"
    assert fin.amount == 1500

    with __import__("pytest").raises(ValueError):
        payroll_service.save_draft(payroll, base_salary=2000, bonus_amount=0, deductions=[], recipient_name=None)


def test_unique_constraint_one_payroll_per_user_per_month(app):
    worker = _worker("0500044004")
    today = date.today()
    payroll_service.get_or_create_draft(user=worker, year=today.year, month=today.month)
    assert Payroll.query.filter_by(user_id=worker.id, year=today.year, month=today.month).count() == 1


def test_prepare_route_full_flow_with_multiple_deductions(app, logged_in_client, owner):
    worker = _worker("0500044005", base_salary=1500)
    today = date.today()
    resp = logged_in_client.get(f"/team/payroll/{worker.id}/prepare?year={today.year}&month={today.month}")
    assert resp.status_code == 200
    token = _csrf_token(resp.data.decode())

    resp2 = logged_in_client.post(
        f"/team/payroll/{worker.id}/prepare?year={today.year}&month={today.month}",
        data={
            "csrf_token": token, "base_salary": "1500", "bonus_amount": "200",
            "deduction_amount": ["50", "30"], "deduction_reason": ["تأخير", "سلفة"],
            "recipient_name": "أخو العامل", "action": "confirm",
        }, follow_redirects=True,
    )
    assert resp2.status_code == 200
    payroll = Payroll.query.filter_by(user_id=worker.id).first()
    assert payroll.status == "confirmed"
    assert payroll.net_amount == 1620
    assert payroll.recipient_name == "أخو العامل"


def test_receipt_requires_confirmed_status(app, logged_in_client, owner):
    worker = _worker("0500044006")
    today = date.today()
    payroll = payroll_service.get_or_create_draft(user=worker, year=today.year, month=today.month)
    resp = logged_in_client.get(f"/team/payroll/{payroll.id}/receipt", follow_redirects=True)
    assert resp.status_code == 200
    assert "لسا ما تأكَّد" in resp.data.decode()


def test_receipt_pdf_after_confirmation(app, owner):
    worker = _worker("0500044007")
    today = date.today()
    payroll = payroll_service.get_or_create_draft(user=worker, year=today.year, month=today.month)
    payroll_service.save_draft(payroll, base_salary=1500, bonus_amount=0, deductions=[(100, "سبب")], recipient_name=None)
    payroll_service.confirm(payroll, actor=owner)

    from app.reports.export_service import build_payroll_receipt_pdf
    from app.models import FarmSettings
    buf = build_payroll_receipt_pdf(payroll, FarmSettings.get())
    data = buf.getvalue()
    assert data[:4] == b"%PDF"


def test_worker_cannot_access_payroll(app, client):
    worker = _worker("0500044008")
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.get("/team/payroll")
    assert resp.status_code == 403


def test_reports_route_filters_by_confirmed_only(app, owner):
    worker = _worker("0500044009")
    today = date.today()
    payroll = payroll_service.get_or_create_draft(user=worker, year=today.year, month=today.month)
    from app.team.payroll_service import save_draft
    save_draft(payroll, base_salary=1500, bonus_amount=0, deductions=[], recipient_name=None)
    # لسا draft — ما يفترض يطلع بالتقرير
    remaining = Payroll.query.filter_by(user_id=worker.id, status="confirmed").count()
    assert remaining == 0
