"""بند إضافي 256 — طلبك الصريح: "كم نسبة أرباحي". قبل هذا البند ما
فيه أي رقم صافي ربح أو نسبة ربح إجمالية بالنظام كله — بس أرقام خام
(إجمالي داخل/خارج). صافي الربح = داخل − خارج، النسبة = الصافي ÷
الخارج × 100. الديون مستثناة (التزام مو دخل/مصروف تشغيلي)."""
from datetime import date

from app.extensions import db
from app.models import Finance


def _row(op_type, amount, cancelled=False):
    db.session.add(Finance(date=date.today(), operation_type=op_type, amount=amount, is_cancelled=cancelled))
    db.session.commit()


def test_net_profit_and_percent_computed(app, logged_in_client):
    _row("sale", 1500)
    _row("purchase", 800)
    _row("expense", 200)

    resp = logged_in_client.get("/finance/")
    assert resp.status_code == 200
    html = resp.data.decode()
    # صافي = 1500 - 1000 = 500 ، النسبة = 500/1000*100 = 50%
    assert "500.00" in html
    assert "50.0%" in html


def test_negative_profit_shown_when_losing(app, logged_in_client):
    _row("sale", 500)
    _row("expense", 1000)

    resp = logged_in_client.get("/finance/")
    html = resp.data.decode()
    assert "-500.00" in html
    assert "-50.0%" in html


def test_debt_rows_excluded_from_profit_calc(app, logged_in_client):
    _row("sale", 1000)
    _row("expense", 500)
    _row("debt_in", 9999)
    _row("debt_repayment", 9999)

    resp = logged_in_client.get("/finance/")
    html = resp.data.decode()
    assert "500.00" in html
    assert "100.0%" in html


def test_cancelled_rows_excluded_from_profit_calc(app, logged_in_client):
    _row("sale", 1000)
    _row("expense", 5000, cancelled=True)

    resp = logged_in_client.get("/finance/")
    html = resp.data.decode()
    # ما فيه مصروف سارٍ — إجمالي الخارج = 0، النسبة ما تُحسب (تقسيم على صفر)
    assert resp.status_code == 200


def test_profit_percent_none_when_no_outflow(app, logged_in_client):
    _row("sale", 1000)
    resp = logged_in_client.get("/finance/")
    assert resp.status_code == 200
    # ما فيه انهيار (تقسيم على صفر) — الشاشة تعرض "-" بدل رقم
    assert "<b style=\"color:#a32d2d;\">-</b>" in resp.data.decode() or "-</b>" in resp.data.decode()
