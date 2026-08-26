"""بند إضافي 252 — بعد نقد صريح: قسم "المالية" بالقائمة الجانبية
يفقد التظليل (ينطوي) لو فتحت أي شاشة فرعية غير الشاشة الرئيسية —
_finance_endpoints كانت ناقصة أغلب شاشات القسم، بخلاف قوائم زي
_feed_endpoints/_team_endpoints المكتملة."""
import re


def _finance_drawer_open(html: str) -> bool:
    idx = html.find(">المالية<")
    assert idx != -1, "لقاء نص 'المالية' بالقائمة الجانبية غير موجود"
    details_idx = html.rfind("<details", 0, idx)
    segment = html[details_idx:idx]
    return " open" in segment or 'open>' in segment or re.search(r"\bopen\b", segment) is not None


def test_finance_drawer_stays_open_on_monthly_cost_report(app, logged_in_client):
    resp = logged_in_client.get("/finance/monthly-cost-report")
    assert resp.status_code == 200
    assert _finance_drawer_open(resp.data.decode())


def test_finance_drawer_stays_open_on_break_even_report(app, logged_in_client):
    resp = logged_in_client.get("/finance/break-even-report")
    assert resp.status_code == 200
    assert _finance_drawer_open(resp.data.decode())


def test_finance_drawer_stays_open_on_lots_list(app, logged_in_client):
    resp = logged_in_client.get("/finance/lots")
    assert resp.status_code == 200
    assert _finance_drawer_open(resp.data.decode())


def test_finance_drawer_stays_open_on_culling_index(app, logged_in_client):
    resp = logged_in_client.get("/finance/culling-index")
    assert resp.status_code == 200
    assert _finance_drawer_open(resp.data.decode())


def test_finance_drawer_stays_open_on_finance_new(app, logged_in_client):
    resp = logged_in_client.get("/finance/new")
    assert resp.status_code == 200
    assert _finance_drawer_open(resp.data.decode())


def test_finance_drawer_closed_on_unrelated_page(app, logged_in_client):
    resp = logged_in_client.get("/team/tasks")
    assert resp.status_code == 200
    assert not _finance_drawer_open(resp.data.decode())
