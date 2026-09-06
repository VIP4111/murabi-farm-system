"""فحص عميق مقسَّم — قسم "الفريق والمهام": مسودة الراتب (`save_draft`)
ما كانت تتحقق إن الراتب الأساسي/المكافأة/كل خصم رقم غير سالب، رغم
إنها تُرحَّل مباشرة لسجل "المالية" كمصروف حقيقي عند التأكيد
(`confirm()`). نفس نمط الثغرة المُصلَحة بالوزن/الحليب/مخزون الدواء."""
import pytest

from app.models import Role, User
from app.team import payroll_service
from datetime import date


def test_negative_base_salary_is_rejected(app):
    with app.app_context():
        role = Role.query.filter_by(name="worker").first()
        user = User(name="عامل", phone="0511111111", role_id=role.id)
        user.set_password("pass1234")
        from app.extensions import db
        db.session.add(user)
        db.session.commit()

        payroll = payroll_service.get_or_create_draft(user=user, year=date.today().year, month=date.today().month)
        with pytest.raises(ValueError, match="سالباً"):
            payroll_service.save_draft(payroll, base_salary=-500, bonus_amount=0, deductions=[], recipient_name=None)


def test_negative_deduction_is_rejected(app):
    with app.app_context():
        role = Role.query.filter_by(name="worker").first()
        user = User(name="عامل٢", phone="0511111112", role_id=role.id)
        user.set_password("pass1234")
        from app.extensions import db
        db.session.add(user)
        db.session.commit()

        payroll = payroll_service.get_or_create_draft(user=user, year=date.today().year, month=date.today().month)
        with pytest.raises(ValueError, match="سالباً"):
            payroll_service.save_draft(
                payroll, base_salary=1000, bonus_amount=0,
                deductions=[(-100, "خصم مقلوب")], recipient_name=None,
            )


def test_normal_payroll_values_are_accepted(app):
    with app.app_context():
        role = Role.query.filter_by(name="worker").first()
        user = User(name="عامل٣", phone="0511111113", role_id=role.id)
        user.set_password("pass1234")
        from app.extensions import db
        db.session.add(user)
        db.session.commit()

        payroll = payroll_service.get_or_create_draft(user=user, year=date.today().year, month=date.today().month)
        payroll_service.save_draft(
            payroll, base_salary=1500, bonus_amount=200,
            deductions=[(50, "غياب")], recipient_name=None,
        )
        assert payroll.net_amount == 1650
