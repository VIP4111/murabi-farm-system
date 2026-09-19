"""فحص شامل سطر بسطر — ميزة المستودعات.

4 مشاكل حقيقية اكتُشفت:
1. جرد صنف عنده كمية موزَّعة فعلياً على مستودع مسمّى، بكمية جرد أقل
   من الموزَّع، كان يُحفَظ بصمت ويخالف قاعدة "مجموع المستودعات = الرصيد
   الإجمالي" — صار يُرفض صراحة الآن.
2. record_count كانت تستخدم date.today() الخام بدل farm_today().
3. item_breakdown/item_transfer بـkind="equipment" كانا يسقطان بخطأ
   500 (KeyError) بدل 404 واضح — الطبقة أصلاً ما تدعم هذا النوع.
4. warehouses_new كانت تحفظ warehouse_type بلا أي فحص مقابل القيم
   المسموحة.
"""
from datetime import date

import pytest

from app.core import inventory_count_service as csvc
from app.core import warehouse_service as wsvc
from app.extensions import db
from app.models import Feed, Warehouse


def _make_feed(name="شعير اختبار مستودعات", available_qty=40):
    item = Feed(name=name, unit="كجم", available_qty=available_qty, unit_price=2.0, status="active")
    db.session.add(item)
    db.session.commit()
    return item


def test_record_count_rejects_actual_below_named_warehouse_allocation(app):
    feed = _make_feed(available_qty=40)
    named_wh = Warehouse(name="مستودع فرعي اختبار", warehouse_type="feed")
    db.session.add(named_wh)
    db.session.commit()
    wsvc.transfer_stock(kind="feed", item_id=feed.id, from_warehouse_id=wsvc.get_or_create_default_warehouse("feed").id,
                         to_warehouse_id=named_wh.id, qty=30, actor_user_id=1)
    # الآن: 30 بالمستودع الفرعي، 10 بالافتراضي (40 إجمالي).
    with pytest.raises(ValueError):
        csvc.record_count(kind="feed", item=feed, actual_qty=20, created_by_id=1)


def test_record_count_still_allows_valid_count_above_named_allocation(app):
    feed = _make_feed(available_qty=40)
    named_wh = Warehouse(name="مستودع فرعي اختبار 2", warehouse_type="feed")
    db.session.add(named_wh)
    db.session.commit()
    wsvc.transfer_stock(kind="feed", item_id=feed.id, from_warehouse_id=wsvc.get_or_create_default_warehouse("feed").id,
                         to_warehouse_id=named_wh.id, qty=30, actor_user_id=1)
    rec = csvc.record_count(kind="feed", item=feed, actual_qty=35, created_by_id=1)
    assert rec.actual_qty == 35
    assert feed.available_qty == 35


def test_record_count_default_date_uses_farm_today(app, monkeypatch):
    fake_farm_date = date(2030, 1, 1)
    monkeypatch.setattr("app.extensions.farm_today", lambda: fake_farm_date)
    feed = _make_feed(available_qty=10)
    rec = csvc.record_count(kind="feed", item=feed, actual_qty=10, created_by_id=1)
    assert rec.count_date == fake_farm_date


def test_item_breakdown_rejects_equipment_kind_with_404_not_500(logged_in_client):
    from app.models import Equipment
    item = Equipment(name="معدة اختبار مستودعات", unit="قطعة", available_qty=5)
    db.session.add(item)
    db.session.commit()
    resp = logged_in_client.get(f"/warehouses/item/equipment/{item.id}")
    assert resp.status_code == 404


def test_warehouses_new_rejects_unknown_warehouse_type(logged_in_client):
    resp = logged_in_client.post("/warehouses/new", data={
        "name": "مستودع اختبار نوع غلط", "warehouse_type": "not_a_real_type",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert Warehouse.query.filter_by(name="مستودع اختبار نوع غلط").first() is None
