"""بند إضافي 254 — طلبك الصريح: "ليش الهامش ما يعتمد على أرقام البيع
الذي يتم عن طريق المزرعة" بدل قيمة يدوية تصدأ. القيمة التقديرية
تُحسب الآن حياً من متوسط أسعار بيع حقيقية لرؤوس مشابهة (نفس النوع/
الجنس، عمر قريب) آخر 90 يوم، وترجع للقيمة اليدوية فقط لو ما فيه
عينة كافية."""
from datetime import date, timedelta

from app.core.animal_profile_service import estimate_market_value_from_comparable_sales, break_even_summary
from app.extensions import db
from app.models import Finance
from factories import make_animal


def _sell(animal, price, when=None):
    db.session.add(Finance(date=when or date.today(), operation_type="sale", amount=price,
                            related_animal_id=animal.id, is_cancelled=False))
    db.session.commit()


def test_no_estimate_when_no_comparable_sales(app):
    a = make_animal(animal_no="MV-01", gender="أنثى")
    assert estimate_market_value_from_comparable_sales(a) is None


def test_estimate_averages_comparable_sales(app):
    target = make_animal(animal_no="MV-02", gender="أنثى")
    sold1 = make_animal(animal_no="MV-03", gender="أنثى", status="sold")
    sold2 = make_animal(animal_no="MV-04", gender="أنثى", status="sold")
    _sell(sold1, 1000)
    _sell(sold2, 1200)

    result = estimate_market_value_from_comparable_sales(target)
    assert result is not None
    assert result["value"] == 1100
    assert result["sample_count"] == 2


def test_estimate_excludes_different_gender(app):
    target = make_animal(animal_no="MV-05", gender="أنثى")
    other_gender = make_animal(animal_no="MV-06", gender="ذكر", status="sold")
    another = make_animal(animal_no="MV-07", gender="ذكر", status="sold")
    _sell(other_gender, 1000)
    _sell(another, 1200)

    assert estimate_market_value_from_comparable_sales(target) is None


def test_estimate_excludes_sales_outside_window(app):
    target = make_animal(animal_no="MV-08", gender="أنثى")
    sold1 = make_animal(animal_no="MV-09", gender="أنثى", status="sold")
    sold2 = make_animal(animal_no="MV-10", gender="أنثى", status="sold")
    _sell(sold1, 1000, when=date.today() - timedelta(days=200))
    _sell(sold2, 1200, when=date.today() - timedelta(days=200))

    assert estimate_market_value_from_comparable_sales(target) is None


def test_estimate_excludes_cancelled_sales(app):
    target = make_animal(animal_no="MV-11", gender="أنثى")
    sold1 = make_animal(animal_no="MV-12", gender="أنثى", status="sold")
    sold2 = make_animal(animal_no="MV-13", gender="أنثى", status="sold")
    db.session.add(Finance(date=date.today(), operation_type="sale", amount=1000,
                            related_animal_id=sold1.id, is_cancelled=True))
    _sell(sold2, 1200)
    db.session.commit()

    result = estimate_market_value_from_comparable_sales(target)
    # بس بيع واحد سارٍ — أقل من الحد الأدنى (2)
    assert result is None


def test_break_even_summary_prefers_auto_estimate_over_manual(app):
    target = make_animal(animal_no="MV-14", gender="أنثى")
    sold1 = make_animal(animal_no="MV-15", gender="أنثى", status="sold")
    sold2 = make_animal(animal_no="MV-16", gender="أنثى", status="sold")
    _sell(sold1, 1000)
    _sell(sold2, 1200)

    from app.core.cycle_engine import get_or_create_workflow
    wf = get_or_create_workflow(target)
    wf.estimated_value = 9999  # قيمة يدوية — ما يفترض تُستخدم لو فيه تقدير تلقائي
    db.session.commit()

    rows = break_even_summary()
    row = next(r for r in rows if r["animal"].animal_no == "MV-14")
    assert row["estimated_value"] == 1100
    assert row["estimate_source"] == "auto"


def test_break_even_summary_falls_back_to_manual_when_no_comparable_sales(app):
    target = make_animal(animal_no="MV-17", gender="أنثى")
    from app.core.cycle_engine import get_or_create_workflow
    wf = get_or_create_workflow(target)
    wf.estimated_value = 1500
    db.session.commit()

    rows = break_even_summary()
    row = next(r for r in rows if r["animal"].animal_no == "MV-17")
    assert row["estimated_value"] == 1500
    assert row["estimate_source"] == "manual"


def test_break_even_report_route_shows_source_labels(app, owner, logged_in_client):
    target = make_animal(animal_no="MV-18", gender="أنثى")
    sold1 = make_animal(animal_no="MV-19", gender="أنثى", status="sold")
    sold2 = make_animal(animal_no="MV-20", gender="أنثى", status="sold")
    _sell(sold1, 1000)
    _sell(sold2, 1200)

    resp = logged_in_client.get("/finance/break-even-report")
    assert resp.status_code == 200
    assert "من 2 مبيعات مشابهة" in resp.data.decode()
