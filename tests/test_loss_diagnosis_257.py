"""بند إضافي 257 — طلبك الصريح: "هل يبين لي سبب الخسارة وطريقة حل
مشكلة الخسارة". صفر نصيحة عامة مختلَقة — يعرض بس حقائق حقيقية من
بياناتك (أكبر بند مصروف، تغيّره عن الفترة السابقة، رؤوس بهامش سالب
فعلياً) لو آخر 30 يوم صافيهم سالب."""
from datetime import date, timedelta

from app.core.loss_diagnosis_service import diagnose_recent_loss
from app.extensions import db
from app.models import Finance


def _row(op_type, amount, category=None, when=None):
    db.session.add(Finance(date=when or date.today(), operation_type=op_type, amount=amount,
                            category=category, is_cancelled=False))
    db.session.commit()


def test_no_diagnosis_when_recent_window_profitable(app):
    _row("sale", 1000)
    _row("expense", 300)
    assert diagnose_recent_loss() is None


def test_diagnosis_appears_when_recent_window_at_loss(app):
    _row("sale", 200)
    _row("expense", 1000, category="علف")
    result = diagnose_recent_loss()
    assert result is not None
    assert result["net"] == -800
    assert result["categories"][0]["category"] == "علف"


def test_category_breakdown_sorted_by_amount_desc(app):
    _row("sale", 100)
    _row("expense", 500, category="علف")
    _row("expense", 200, category="دواء")
    result = diagnose_recent_loss()
    cats = [c["category"] for c in result["categories"]]
    assert cats == ["علف", "دواء"]
    assert result["categories"][0]["percent_of_total"] == round(500 / 700 * 100, 1)


def test_change_percent_compares_to_prior_window(app):
    prior_start = date.today() - timedelta(days=45)
    _row("expense", 200, category="علف", when=prior_start)  # الفترة السابقة
    _row("expense", 400, category="علف")  # الفترة الحالية — ضعف
    _row("sale", 10)

    result = diagnose_recent_loss()
    olaf = next(c for c in result["categories"] if c["category"] == "علف")
    assert olaf["change_pct"] == 100  # زاد 100%


def test_new_category_this_period_has_none_change(app):
    _row("expense", 300, category="جديد")
    _row("sale", 10)
    result = diagnose_recent_loss()
    cat = next(c for c in result["categories"] if c["category"] == "جديد")
    assert cat["change_pct"] is None


def test_cancelled_rows_excluded(app):
    db.session.add(Finance(date=date.today(), operation_type="expense", amount=5000,
                            category="علف", is_cancelled=True))
    db.session.add(Finance(date=date.today(), operation_type="sale", amount=1, is_cancelled=False))
    db.session.commit()
    assert diagnose_recent_loss() is None


def test_at_risk_animal_count_included(app):
    from app.core.animal_service import create_animal
    from app.models.animal import AnimalSource
    from app.core.cycle_engine import get_or_create_workflow
    animal = create_animal(animal_no="LD-01", source=AnimalSource.PURCHASE, gender="ذكر", price=5000)
    wf = get_or_create_workflow(animal)
    wf.estimated_value = 1  # أقل بكثير من التكلفة — هامش سالب
    db.session.commit()

    _row("sale", 10)
    _row("expense", 1000, category="علف")

    result = diagnose_recent_loss()
    assert result["at_risk_count"] >= 1


def test_finance_list_route_shows_diagnosis_card(app, logged_in_client):
    _row("sale", 100)
    _row("expense", 900, category="علف")

    resp = logged_in_client.get("/finance/")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "ليش أنا بخسارة" in html
    assert "علف" in html


def test_finance_list_route_hides_diagnosis_when_profitable(app, logged_in_client):
    _row("sale", 1000)
    _row("expense", 100)

    resp = logged_in_client.get("/finance/")
    assert resp.status_code == 200
    assert "ليش أنا بخسارة" not in resp.data.decode()
