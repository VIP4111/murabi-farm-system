"""اختبار بند التصميم "بلاطات مراح" (طلبك: "استمر حتى تغطي كل
الشاشات") — دفعة ثالثة: تشخيص الحمل، مكوّنات العلف، الأصول،
المستودعات، دفعات استقبال القطيع."""
from datetime import date

from app.extensions import db
from app.models import Feed, Warehouse
from app.models.animal_batch import AnimalBatch
from app.models.asset import Asset
from app.models.repro import Pregnancy
from tests.factories import make_animal, make_barn


def test_pregnancies_list_shows_pregnancy_chip(logged_in_client):
    barn = make_barn()
    female = make_animal(animal_no="F-01", gender="أنثى", barn_id=barn.id)
    p = Pregnancy(female_id=female.id, date=date.today(), confirmed=True)
    db.session.add(p)
    db.session.commit()

    resp = logged_in_client.get("/repro/pregnancies")
    assert resp.status_code == 200
    assert b"pregnancy-chip" in resp.data


def test_feed_items_list_shows_feed_class_chip(logged_in_client):
    item = Feed(name="علف اختبار", available_qty=10, unit="كجم", status="active", feed_class="concentrate")
    db.session.add(item)
    db.session.commit()

    resp = logged_in_client.get("/feed/items")
    assert resp.status_code == 200
    assert b"feed-class-chip" in resp.data


def test_assets_list_shows_category_chip(logged_in_client):
    asset = Asset(name="أصل اختبار", category="generator")
    db.session.add(asset)
    db.session.commit()

    resp = logged_in_client.get("/equipment/assets")
    assert resp.status_code == 200
    assert b"asset-category-chip" in resp.data


def test_warehouses_list_shows_type_chip(logged_in_client):
    w = Warehouse(name="مستودع اختبار", warehouse_type="feed")
    db.session.add(w)
    db.session.commit()

    resp = logged_in_client.get("/warehouses/")
    assert resp.status_code == 200
    assert b"warehouse-type-chip" in resp.data


def test_batches_list_shows_stage_chip(logged_in_client):
    b = AnimalBatch(batch_no="B-TEST-01", source="purchase", stage=1, arrival_date=date.today())
    db.session.add(b)
    db.session.commit()

    resp = logged_in_client.get("/batches/")
    assert resp.status_code == 200
    assert b"batch-stage-chip" in resp.data
