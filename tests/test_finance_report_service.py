"""اختبارات app/core/finance_report_service.py — تكلفة الرأس الشهرية
والإجمالي السنوي (بند إضافي 46، القسم ٤؛ ودقة تاريخية حقيقية بدل
تقريب "العدد الحالي لكل الأشهر" — بند إضافي 251)."""
from datetime import date, timedelta

from app.core.finance_report_service import monthly_cost_per_head, annual_cost_per_head
from app.extensions import db
from app.models import Finance, CycleEvent
from factories import make_animal


def _add_expense(amount, is_indirect=False, when=None):
    row = Finance(date=when or date.today(), operation_type="expense", amount=amount, is_indirect=is_indirect)
    db.session.add(row)
    db.session.commit()
    return row


def _months_ago(n):
    today = date.today()
    y, m = today.year, today.month - n
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1)


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


def test_animal_purchased_this_month_not_counted_in_earlier_months(app):
    """بند إضافي 251 — رأس اشتُري هالشهر ما يفترض يُحسب بأشهر قبله،
    مو زي السلوك القديم اللي كان يستخدم نفس العدد الحالي لكل الأشهر."""
    make_animal(animal_no="F-05")  # purchase_date = اليوم
    rows = monthly_cost_per_head(months=3)
    assert rows[0]["head_count"] == 1  # الشهر الحالي
    assert rows[1]["head_count"] == 0  # شهر قبل الشراء
    assert rows[2]["head_count"] == 0


def test_animal_sold_in_past_month_excluded_from_later_months(app):
    """بند إضافي 251 — رأس دخل قبل 3 أشهر وانباع قبل شهر، يُحسب
    بالأشهر بينهم بس، مو بعد بيعه."""
    animal = make_animal(animal_no="F-06")
    animal.purchase_date = _months_ago(3)
    db.session.add(CycleEvent(animal_id=animal.id, event_type="sale", stage_index=10,
                               event_date=_months_ago(1)))
    db.session.commit()

    rows = monthly_cost_per_head(months=4)
    # rows[0] = الشهر الحالي (بعد البيع) — ما يُحسب
    assert rows[0]["head_count"] == 0
    # rows[1] = شهر البيع نفسه (لسا كان موجود أول الشهر) — يُحسب
    assert rows[1]["head_count"] == 1
    # rows[2], rows[3] = أشهر قبل البيع، بعد الشراء — يُحسب
    assert rows[2]["head_count"] == 1
    assert rows[3]["head_count"] == 1


def test_dead_animal_excluded_after_death_month(app):
    animal = make_animal(animal_no="F-07")
    animal.purchase_date = _months_ago(2)
    db.session.add(CycleEvent(animal_id=animal.id, event_type="death", stage_index=10,
                               event_date=_months_ago(1)))
    db.session.commit()

    rows = monthly_cost_per_head(months=3)
    assert rows[0]["head_count"] == 0


def test_annual_cost_per_head_uses_average_across_variable_months(app):
    """بند إضافي 251 — بعد ما صار عدد الرؤوس يتغيّر شهر لشهر، الإجمالي
    السنوي يستخدم متوسط العدد عبر الأشهر، مو رقم شهر واحد ثابت."""
    animal1 = make_animal(animal_no="F-08")
    animal1.purchase_date = _months_ago(3)
    animal2 = make_animal(animal_no="F-09")  # اشترى هالشهر بس
    db.session.commit()
    _add_expense(120)

    rows = monthly_cost_per_head(months=3)
    # الشهر الحالي: رأسين، الشهرين قبله: رأس واحد بس
    assert [r["head_count"] for r in rows] == [2, 1, 1]

    annual = annual_cost_per_head(rows)
    assert annual["head_count"] == round((2 + 1 + 1) / 3, 1)
    assert annual["total_cost"] == 120
    assert annual["months_count"] == 3


def test_annual_cost_per_head_handles_no_animals(app):
    annual = annual_cost_per_head(monthly_cost_per_head(months=1))
    assert annual["cost_per_head"] is None
