"""فحص عميق — قسم الفريق والمهام: `payroll_service.confirm()` كانت
تُرحّل `net_amount` لسجل "المالية" كمصروف بدون أي فحص — لو مجموع
الخصومات تجاوز الراتب الأساسي + المكافأة، `net_amount` يصير سالباً،
ويُرحَّل كما هو كمصروف بمبلغ سالب — يعني عملياً **يقلّل** إجمالي
المصروفات المعروضة بدل ما يعكس راتباً حقيقياً."""
import pytest
from datetime import date

from app.extensions import db
from app.team import payroll_service
from app.models import Payroll, Finance, Role, User


def _worker(phone, base_salary=500):
    role = Role.query.filter_by(name="worker").first()
    u = User(name=f"عامل {phone}", phone=phone, role_id=role.id, language="ar", base_salary=base_salary)
    u.set_password("pass1234")
    db.session.add(u)
    db.session.commit()
    return u


def test_confirm_rejects_negative_net_amount(app):
    worker = _worker("0500055001", base_salary=500)
    today = date.today()
    payroll = payroll_service.get_or_create_draft(user=worker, year=today.year, month=today.month)
    # خصم أكبر بكثير من الراتب + المكافأة — صافي سالب
    payroll_service.save_draft(
        payroll, base_salary=500, bonus_amount=0,
        deductions=[(2000, "خصم غير منطقي")], recipient_name=None,
    )

    with pytest.raises(ValueError):
        payroll_service.confirm(payroll, actor=worker)

    finance_count_before = Finance.query.filter_by(category="راتب موظف").count()
    assert finance_count_before == 0, "عملية مالية انترحّلت رغم إن التأكيد يفترض يُرفض"
    db.session.refresh(payroll)
    assert payroll.status == "draft"


def test_confirm_accepts_non_negative_net_amount(app):
    worker = _worker("0500055002", base_salary=1000)
    today = date.today()
    payroll = payroll_service.get_or_create_draft(user=worker, year=today.year, month=today.month)
    payroll_service.save_draft(
        payroll, base_salary=1000, bonus_amount=0,
        deductions=[(200, "خصم عادي")], recipient_name=None,
    )

    payroll_service.confirm(payroll, actor=worker)

    db.session.refresh(payroll)
    assert payroll.status == "confirmed"
    assert payroll.net_amount == 800
