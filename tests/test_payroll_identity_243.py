"""بند إضافي 243 — بيانات هوية العامل (جنسية/جواز/حدود/طريقة دفع)
ورقم هوية صاحب العمل، بطلبك الصريح بعد ما شاركت نموذج "مسير راتب
عامل منزلي" رسمي كمرجع شكل. تُدخَل يدوياً مرة وحدة، تظهر تلقائياً
بكل وصل راتب بعدها."""
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


def test_salary_update_saves_identity_fields(app, logged_in_client):
    worker = _worker("0500055001")
    resp = logged_in_client.post(f"/team/salaries/{worker.id}/update", data={
        "base_salary": "1300", "nationality": "إثيوبيا",
        "passport_number": "EP1234567", "border_number": "9988776655",
        "payment_method": "نقداً",
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(worker)
    assert worker.nationality == "إثيوبيا"
    assert worker.passport_number == "EP1234567"
    assert worker.border_number == "9988776655"
    assert worker.payment_method == "نقداً"


def test_farm_identity_save_stores_owner_national_id(app, logged_in_client):
    resp = logged_in_client.post("/settings/farm-identity", data={
        "farm_name": "مراح بو علي", "owner_national_id": "1014962771",
    }, follow_redirects=True)
    assert resp.status_code == 200
    fs = FarmSettings.get()
    assert fs.owner_national_id == "1014962771"


def test_receipt_pdf_includes_identity_fields_when_present(app, owner):
    worker = _worker("0500055002")
    worker.nationality = "إثيوبيا"
    worker.passport_number = "EP7127204"
    worker.border_number = "3566608711"
    worker.payment_method = "نقداً"
    db.session.commit()

    fs = FarmSettings.get()
    fs.owner_national_id = "1014962771"
    db.session.commit()

    today = date.today()
    payroll = payroll_service.get_or_create_draft(user=worker, year=today.year, month=today.month)
    payroll_service.save_draft(payroll, base_salary=1300, bonus_amount=0, deductions=[], recipient_name=None)
    payroll_service.confirm(payroll, actor=owner)

    from app.reports.export_service import build_payroll_receipt_pdf
    buf = build_payroll_receipt_pdf(payroll, fs)
    data = buf.getvalue()
    assert data[:4] == b"%PDF"
    assert len(data) > 1000


def test_receipt_pdf_works_without_identity_fields(app, owner):
    """الحقول اختيارية تماماً — وصل بدونها لازم يشتغل عادي بدون خطأ."""
    worker = _worker("0500055003")
    today = date.today()
    payroll = payroll_service.get_or_create_draft(user=worker, year=today.year, month=today.month)
    payroll_service.save_draft(payroll, base_salary=1300, bonus_amount=0, deductions=[], recipient_name=None)
    payroll_service.confirm(payroll, actor=owner)

    from app.reports.export_service import build_payroll_receipt_pdf
    buf = build_payroll_receipt_pdf(payroll, FarmSettings.get())
    assert buf.getvalue()[:4] == b"%PDF"
