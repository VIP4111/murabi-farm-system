"""بند إضافي 262 — بطلبك "العلف والمستودعات"، راجعت القسم بعمق. لقيت
نفس خلل القائمة الجانبية (بند 252/258): شاشات "الخلطات" (rations)،
"شراء علف"، وأغلب شاشات المستودعات الفرعية كانت غايبة عن
_feed_endpoints. راجعت الربط المالي (شراء العلف، جرد المخزون/الهالك)
ولقيتها موصولة صح أصلاً — بند 203 و"الهالك" (inventory_count_service)
كلاهما يسجّلان Finance حقيقية، ما فيه فجوة مشابهة لبند 259/261 هنا."""
from factories import make_feed


def _drawer_open(html: str) -> bool:
    # بند إضافي 318 — عنوان المجموعة صار "التغذية والأعلاف" بعد إعادة
    # هيكلة القائمة الجانبية لـ5 مراكز رئيسية (نفس الرابط/الصلاحية،
    # تسمية فقط).
    idx = html.find(">التغذية والأعلاف<")
    assert idx != -1
    details_idx = html.rfind("<details", 0, idx)
    return " open" in html[details_idx:idx]


def test_feed_drawer_stays_open_on_rations_list(app, logged_in_client):
    resp = logged_in_client.get("/feed/rations")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_feed_drawer_stays_open_on_rations_new(app, logged_in_client):
    resp = logged_in_client.get("/feed/rations/new")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_feed_drawer_stays_open_on_ration_detail(app, logged_in_client):
    from app.extensions import db
    from app.models import FeedRation
    ration = FeedRation(name="خلطة اختبار")
    db.session.add(ration)
    db.session.commit()
    resp = logged_in_client.get(f"/feed/rations/{ration.id}")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_feed_drawer_stays_open_on_purchase_new(app, logged_in_client):
    resp = logged_in_client.get("/feed/purchase")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_feed_drawer_stays_open_on_warehouses_new(app, logged_in_client):
    resp = logged_in_client.get("/warehouses/new")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_feed_drawer_stays_open_on_item_breakdown(app, logged_in_client):
    item = make_feed()
    resp = logged_in_client.get(f"/warehouses/item/feed/{item.id}")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_feed_drawer_stays_open_on_item_count(app, logged_in_client):
    item = make_feed()
    resp = logged_in_client.get(f"/warehouses/item/feed/{item.id}/count")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_feed_drawer_stays_open_on_inventory_counts_list(app, logged_in_client):
    resp = logged_in_client.get("/warehouses/inventory-counts")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())
