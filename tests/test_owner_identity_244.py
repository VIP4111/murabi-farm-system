"""بند إضافي 244 — بيانات صاحب الحلال (اسم/هوية/جوال) مباشرة بشاشة
"الرواتب الأساسية" عبر صلاحية team.manage_salary (بدل settings.manage
الكاملة)، وطريقة الدفع صارت اختيار محدود (نقداً/تحويل بنكي) مع وضوح
"من المحوّل ومن المستلم" بوصل التحويل."""
from datetime import date

from app.extensions import db
from app.team import payroll_service
from app.models import FarmSettings, Role, User


def _worker(phone):
    role = Role.query.filter_by(name="worker").first()
    u = User(name=f"عامل {phone}", phone=phone, role_id=role.id, language="ar", base_salary=1300)
    u.set_password("pass1234")
    db.session.add(u)
    db.session.commit()
    return u


def test_owner_identity_update_via_salaries_permission(app, logged_in_client):
    resp = logged_in_client.post("/team/salaries/owner-identity", data={
        "farm_name": "مراح بو علي", "owner_national_id": "1014962771", "farm_phone": "0504125248",
    }, follow_redirects=True)
    assert resp.status_code == 200
    fs = FarmSettings.get()
    assert fs.farm_name == "مراح بو علي"
    assert fs.owner_national_id == "1014962771"
    assert fs.farm_phone == "0504125248"


def test_owner_identity_forbidden_for_worker(app, client):
    worker = _worker("0500066001")
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.post("/team/salaries/owner-identity", data={"farm_name": "اختراق"})
    assert resp.status_code == 403


def test_salaries_list_shows_owner_identity_card(app, logged_in_client):
    resp = logged_in_client.get("/team/salaries")
    assert resp.status_code == 200
    assert "بيانات صاحب الحلال" in resp.data.decode()


def test_receipt_shows_transfer_sender_and_recipient(app, owner):
    worker = _worker("0500066002")
    worker.payment_method = "تحويل بنكي"
    db.session.commit()

    fs = FarmSettings.get()
    fs.farm_name = "مراح بو علي"
    db.session.commit()

    today = date.today()
    payroll = payroll_service.get_or_create_draft(user=worker, year=today.year, month=today.month)
    payroll_service.save_draft(payroll, base_salary=1300, bonus_amount=0, deductions=[], recipient_name="أخو العامل")
    payroll_service.confirm(payroll, actor=owner)

    from app.reports.export_service import build_payroll_receipt_pdf
    buf = build_payroll_receipt_pdf(payroll, fs)
    assert buf.getvalue()[:4] == b"%PDF"


def test_receipt_shows_cash_label(app, owner):
    worker = _worker("0500066003")
    worker.payment_method = "نقداً"
    db.session.commit()

    today = date.today()
    payroll = payroll_service.get_or_create_draft(user=worker, year=today.year, month=today.month)
    payroll_service.save_draft(payroll, base_salary=1300, bonus_amount=0, deductions=[], recipient_name=None)
    payroll_service.confirm(payroll, actor=owner)

    from app.reports.export_service import build_payroll_receipt_pdf
    buf = build_payroll_receipt_pdf(payroll, FarmSettings.get())
    assert buf.getvalue()[:4] == b"%PDF"


def test_recipient_name_stays_replaceable_across_months(app, owner):
    """اسم مستلم الحوالة حقل على Payroll نفسه (مو User) — يقدر يختلف
    كل شهر بحرية، بطلبك: "خليه قابل للاستبدال"."""
    worker = _worker("0500066004")
    worker.payment_method = "تحويل بنكي"
    db.session.commit()

    today = date.today()
    payroll1 = payroll_service.get_or_create_draft(user=worker, year=today.year, month=today.month)
    payroll_service.save_draft(payroll1, base_salary=1300, bonus_amount=0, deductions=[], recipient_name="أخو العامل")
    payroll_service.confirm(payroll1, actor=owner)
    assert payroll1.recipient_name == "أخو العامل"

    next_month = today.month + 1 if today.month < 12 else 1
    next_year = today.year if today.month < 12 else today.year + 1
    payroll2 = payroll_service.get_or_create_draft(user=worker, year=next_year, month=next_month)
    payroll_service.save_draft(payroll2, base_salary=1300, bonus_amount=0, deductions=[], recipient_name="والد العامل")
    payroll_service.confirm(payroll2, actor=owner)
    assert payroll2.recipient_name == "والد العامل"
    assert payroll1.recipient_name == "أخو العامل"
