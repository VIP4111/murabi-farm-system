"""اختبارات نواقص الصيدلية (بند إضافي 48، القسم الأول-٢) — على مستوى
Route لأن منطق الاستعلام والبدائل مبني بالراوت نفسه، مو دالة خدمة منفصلة."""
from app.extensions import db
from app.models import Pharmacy
from factories import make_pharmacy


def test_shortage_list_only_shows_items_at_or_below_threshold(app, logged_in_client):
    low = make_pharmacy(name="دواء ناقص", available_qty=2)
    low.min_stock_qty = 5
    db.session.commit()
    make_pharmacy(name="دواء وفير", available_qty=100)  # min_stock_qty default 0 -> not short

    resp = logged_in_client.get("/health/pharmacy/shortages")
    assert resp.status_code == 200
    assert "دواء ناقص".encode() in resp.data
    assert "دواء وفير".encode() not in resp.data


def test_shortage_list_suggests_same_category_alternative(app, logged_in_client):
    short_item = Pharmacy(name="مضاد حيوي أ", category="مضاد حيوي", available_qty=0, min_stock_qty=5, status="active")
    healthy_alt = Pharmacy(name="مضاد حيوي ب", category="مضاد حيوي", available_qty=50, min_stock_qty=5, status="active")
    other_category = Pharmacy(name="فيتامين", category="فيتامين", available_qty=50, min_stock_qty=5, status="active")
    db.session.add_all([short_item, healthy_alt, other_category])
    db.session.commit()

    resp = logged_in_client.get("/health/pharmacy/shortages")
    assert resp.status_code == 200
    assert "مضاد حيوي ب".encode() in resp.data
    assert "فيتامين".encode() not in resp.data


def test_shortage_list_empty_when_nothing_short(app, logged_in_client):
    make_pharmacy(name="دواء وفير", available_qty=100)
    resp = logged_in_client.get("/health/pharmacy/shortages")
    assert resp.status_code == 200
    assert "لا يوجد نواقص".encode() in resp.data
