"""بند إضافي 161 — كشف الشذوذ المالي: مقارنة عملية جديدة بمتوسط
تاريخها الفعلي بنفس النوع والفئة."""
from datetime import date

from app.extensions import db
from app.models import Finance
from app.core.finance_anomaly_service import detect_anomaly


def _add_finance(operation_type="purchase", category="علف", amount=100.0):
    row = Finance(date=date.today(), operation_type=operation_type, category=category, amount=amount)
    db.session.add(row)
    db.session.commit()
    return row


def test_no_anomaly_without_enough_history(app):
    _add_finance(amount=100)
    _add_finance(amount=100)
    new = _add_finance(amount=1000)  # بس 2 سجل تاريخي — أقل من الحد الأدنى
    assert detect_anomaly(new) is None


def test_no_anomaly_without_category(app):
    row = Finance(date=date.today(), operation_type="purchase", category=None, amount=1000)
    db.session.add(row)
    db.session.commit()
    assert detect_anomaly(row) is None


def test_no_anomaly_when_amount_close_to_average(app):
    for _ in range(4):
        _add_finance(amount=100)
    new = _add_finance(amount=120)  # 20% فرق بس — تحت الحد
    assert detect_anomaly(new) is None


def test_detects_anomaly_when_amount_much_higher(app):
    for _ in range(4):
        _add_finance(amount=100)
    new = _add_finance(amount=500)
    result = detect_anomaly(new)
    assert result is not None
    assert result["direction"] == "أعلى"
    assert result["deviation_pct"] > 50


def test_detects_anomaly_when_amount_much_lower(app):
    for _ in range(4):
        _add_finance(amount=100)
    new = _add_finance(amount=20)
    result = detect_anomaly(new)
    assert result is not None
    assert result["direction"] == "أقل"


def test_cancelled_entries_excluded_from_history(app):
    for _ in range(4):
        row = _add_finance(amount=100)
    row.is_cancelled = True
    db.session.commit()
    # بعد إلغاء واحد، الباقي 3 (لا يزال يحقق الحد الأدنى)
    new = _add_finance(amount=500)
    result = detect_anomaly(new)
    assert result is not None


def test_different_category_does_not_count_as_history(app):
    for _ in range(4):
        _add_finance(category="علف", amount=100)
    new = _add_finance(category="دواء", amount=100)  # فئة جديدة، ما لها تاريخ
    assert detect_anomaly(new) is None
