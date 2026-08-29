"""بند إضافي 255 — شارت موسمية أسعار البيع بالتقويم الهجري. طلبك:
أفضل شهر للبيع مرتبط بالمواسم الدينية (تتحرك بالهجري لا الميلادي)،
وكل رقم مبني على مبيعات حقيقية سجّلتها المزرعة — صفر بيانات مختلَقة
أو اتصال بسوق خارجي."""
from datetime import date

from app.core.seasonal_price_service import seasonal_price_analysis, _to_hijri, HIJRI_MONTH_NAMES_AR
from app.extensions import db
from app.models import Finance


def _sale(amount, when):
    db.session.add(Finance(date=when, operation_type="sale", amount=amount, is_cancelled=False))
    db.session.commit()


def test_no_sales_returns_empty_analysis(app):
    data = seasonal_price_analysis()
    assert data["total_sales_count"] == 0
    assert data["data_years_count"] == 0
    assert data["sufficient_data"] is False
    assert all(m["current_year_avg"] is None for m in data["months"])


def test_cancelled_sale_excluded(app):
    row = Finance(date=date.today(), operation_type="sale", amount=1000, is_cancelled=True)
    db.session.add(row)
    db.session.commit()

    data = seasonal_price_analysis()
    assert data["total_sales_count"] == 0


def test_current_year_average_computed_for_todays_hijri_month(app):
    _sale(1000, date.today())
    _sale(1200, date.today())

    data = seasonal_price_analysis()
    hy, hm = _to_hijri(date.today())
    month_row = next(m for m in data["months"] if m["hijri_month"] == hm)
    assert month_row["current_year_avg"] == 1100
    assert month_row["current_year_count"] == 2
    assert month_row["historical_avg"] == 1100  # نفس البيانات، سنة وحدة بس
    assert data["data_years_count"] == 1
    assert data["sufficient_data"] is False  # سنة وحدة، تحت الحد الأدنى (2)


def test_religious_season_months_flagged(app):
    data = seasonal_price_analysis()
    ramadan = next(m for m in data["months"] if m["hijri_month"] == 9)
    dhul_hijjah = next(m for m in data["months"] if m["hijri_month"] == 12)
    muharram = next(m for m in data["months"] if m["hijri_month"] == 1)
    assert ramadan["is_religious_season"] is True
    assert dhul_hijjah["is_religious_season"] is True
    assert muharram["is_religious_season"] is False


def test_month_names_are_arabic_hijri(app):
    assert HIJRI_MONTH_NAMES_AR[9] == "رمضان"
    assert HIJRI_MONTH_NAMES_AR[12] == "ذو الحجة"


def test_route_renders_with_no_data(app, logged_in_client):
    resp = logged_in_client.get("/finance/seasonal-price-analysis")
    assert resp.status_code == 200
    assert "ما فيه عمليات بيع مسجَّلة بعد" in resp.data.decode()


def test_route_renders_with_data_and_shows_insufficient_warning(app, logged_in_client):
    _sale(1000, date.today())
    _sale(1200, date.today())

    resp = logged_in_client.get("/finance/seasonal-price-analysis")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "سنة هجرية بس" in html
    assert "1100.00" in html


def test_finance_drawer_stays_open_on_seasonal_analysis(app, logged_in_client):
    resp = logged_in_client.get("/finance/seasonal-price-analysis")
    assert resp.status_code == 200
    # بند إضافي 318 — عنوان المجموعة صار "المالية والمبيعات"
    idx = resp.data.decode().find(">المالية والمبيعات<")
    assert idx != -1
