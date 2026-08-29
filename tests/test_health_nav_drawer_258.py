"""بند إضافي 258 — بداية إصلاح نفس خلل بند 252 بقسم "الصحة" (أوسع
بكثير هناك: 42 راوت فعلي مقابل 11 بس بالقائمة). أول 4 شاشات بطلبك
الصريح: نواقص الصيدلية، دواء جديد، تعديل دواء، شراء دواء."""
from factories import make_pharmacy


def _drawer_open(html: str) -> bool:
    # بند إضافي 318 — عنوان المجموعة صار "الصحة والتحصين" بعد إعادة
    # هيكلة القائمة الجانبية لـ5 مراكز رئيسية (نفس الرابط/الصلاحية،
    # تسمية فقط).
    idx = html.find(">الصحة والتحصين<")
    assert idx != -1
    details_idx = html.rfind("<details", 0, idx)
    return " open" in html[details_idx:idx]


def test_health_drawer_stays_open_on_pharmacy_shortages(app, logged_in_client):
    resp = logged_in_client.get("/health/pharmacy/shortages")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_health_drawer_stays_open_on_pharmacy_new(app, logged_in_client):
    resp = logged_in_client.get("/health/pharmacy/new")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_health_drawer_stays_open_on_pharmacy_edit(app, logged_in_client):
    item = make_pharmacy()
    resp = logged_in_client.get(f"/health/pharmacy/{item.id}/edit")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_health_drawer_stays_open_on_pharmacy_purchase(app, logged_in_client):
    item = make_pharmacy()
    resp = logged_in_client.get(f"/health/pharmacy/{item.id}/purchase")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_health_drawer_closed_on_unrelated_page(app, logged_in_client):
    resp = logged_in_client.get("/team/tasks")
    assert resp.status_code == 200
    assert not _drawer_open(resp.data.decode())
