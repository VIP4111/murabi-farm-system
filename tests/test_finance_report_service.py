"""اختبارات app/core/finance_report_service.py — تكلفة الرأس الشهرية
والإجمالي السنوي (بند إضافي 46، القسم ٤)."""
from datetime import date

from app.core.finance_report_service import monthly_cost_per_head, annual_cost_per_head
from app.extensions import db
from app.models import Finance
from factories import make_animal


def _add_expense(amount, is_indirect=False, when=None):
    row = Finance(date=when or date.today(), operation_type="expense", amount=amount, is_indirect=is_indirect)
    db.session.add(row)
    db.session.commit()
    return row


def test_monthly_cost_per_head_splits_evenly_across_active_heads(app):
    make_animal(animal_no="F-01")
    make_animal(animal_no="F-02")
    _add_expense(200)

    rows = monthly_cost_per_head(months=1)
    assert rows[0]["head_count"] == 2
    assert rows[0]["total_cost"] == 200
    assert rows[0]["cost_per_head"] == 100


def test_monthly_cost_excludes_sale_and_debt_rows(app):
    make_animal(animal_no="F-03")
    _add_expense(100)
    db.session.add(Finance(date=date.today(), operation_type="sale", amount=9999))
    db.session.add(Finance(date=date.today(), operation_type="debt_in", amount=5000))
    db.session.commit()

    rows = monthly_cost_per_head(months=1)
    assert rows[0]["total_cost"] == 100


def test_cancelled_expense_excluded(app):
    make_animal(animal_no="F-04")
    row = _add_expense(150)
    row.is_cancelled = True
    db.session.commit()

    rows = monthly_cost_per_head(months=1)
    assert rows[0]["total_cost"] == 0


def test_annual_cost_per_head_aggregates_all_months(app):
    make_animal(animal_no="F-05")
    make_animal(animal_no="F-06")
    _add_expense(100)

    rows = monthly_cost_per_head(months=12)
    annual = annual_cost_per_head(rows)
    assert annual["total_cost"] == 100
    assert annual["head_count"] == 2
    assert annual["cost_per_head"] == 50
    assert annual["months_count"] == 12


def test_annual_cost_per_head_handles_no_animals(app):
    annual = annual_cost_per_head(monthly_cost_per_head(months=1))
    assert annual["cost_per_head"] is None
