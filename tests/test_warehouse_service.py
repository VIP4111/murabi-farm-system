"""اختبارات تعدد المستودعات (بند إضافي 52، جزء 3) — طبقة إضافية فوق
الإجمالي: المستودع الافتراضي محسوب كباقي (الإجمالي ناقص المستودعات
المسمّاة)، والتحويل الصريح لا يغيّر الإجمالي إطلاقاً — نتحقق من هذا
الثبات صراحة، بالإضافة لكون available_qty الأصلي غير متأثر بأي شكل."""
import pytest

from app.core import warehouse_service as wsvc
from app.extensions import db
from app.models import Warehouse
from factories import make_feed, make_pharmacy


def _named_warehouse(kind="feed", name="مستودع فرعي"):
    w = Warehouse(name=name, warehouse_type=kind, is_default=False)
    db.session.add(w)
    db.session.commit()
    return w


def test_breakdown_starts_all_in_default_warehouse(app):
    feed = make_feed(name="علف 1", available_qty=100)
    breakdown = wsvc.warehouse_breakdown(feed, "feed")
    assert len(breakdown) == 1
    assert breakdown[0]["is_default"] is True
    assert breakdown[0]["qty"] == 100


def test_transfer_moves_qty_without_touching_available_qty(app):
    feed = make_feed(name="علف 2", available_qty=100)
    sub = _named_warehouse(name="حظيرة تغذية مباشرة")
    default_wh = wsvc.get_or_create_default_warehouse("feed")

    wsvc.transfer_stock(kind="feed", item_id=feed.id, from_warehouse_id=default_wh.id,
                         to_warehouse_id=sub.id, qty=30, actor_user_id=1)

    assert feed.available_qty == 100  # الإجمالي ما تغيّر إطلاقاً
    breakdown = {e["warehouse"].id: e["qty"] for e in wsvc.warehouse_breakdown(feed, "feed")}
    assert breakdown[default_wh.id] == 70
    assert breakdown[sub.id] == 30


def test_transfer_between_two_named_warehouses(app):
    feed = make_feed(name="علف 3", available_qty=50)
    default_wh = wsvc.get_or_create_default_warehouse("feed")
    wh_a = _named_warehouse(name="مستودع أ")
    wh_b = _named_warehouse(name="مستودع ب")
    wsvc.transfer_stock(kind="feed", item_id=feed.id, from_warehouse_id=default_wh.id,
                         to_warehouse_id=wh_a.id, qty=20, actor_user_id=1)

    wsvc.transfer_stock(kind="feed", item_id=feed.id, from_warehouse_id=wh_a.id,
                         to_warehouse_id=wh_b.id, qty=8, actor_user_id=1)

    breakdown = {e["warehouse"].id: e["qty"] for e in wsvc.warehouse_breakdown(feed, "feed")}
    assert breakdown[wh_a.id] == 12
    assert breakdown[wh_b.id] == 8
    assert breakdown[default_wh.id] == 30
    assert feed.available_qty == 50


def test_transfer_rejects_more_than_available_in_source(app):
    feed = make_feed(name="علف 4", available_qty=10)
    default_wh = wsvc.get_or_create_default_warehouse("feed")
    sub = _named_warehouse(name="مستودع ج")
    with pytest.raises(ValueError):
        wsvc.transfer_stock(kind="feed", item_id=feed.id, from_warehouse_id=default_wh.id,
                             to_warehouse_id=sub.id, qty=999, actor_user_id=1)


def test_transfer_rejects_same_source_and_destination(app):
    feed = make_feed(name="علف 5", available_qty=10)
    default_wh = wsvc.get_or_create_default_warehouse("feed")
    with pytest.raises(ValueError):
        wsvc.transfer_stock(kind="feed", item_id=feed.id, from_warehouse_id=default_wh.id,
                             to_warehouse_id=default_wh.id, qty=1, actor_user_id=1)


def test_breakdown_sum_always_equals_available_qty(app):
    feed = make_feed(name="علف 6", available_qty=200)
    default_wh = wsvc.get_or_create_default_warehouse("feed")
    wh1 = _named_warehouse(name="فرعي 1")
    wh2 = _named_warehouse(name="فرعي 2")
    wsvc.transfer_stock(kind="feed", item_id=feed.id, from_warehouse_id=default_wh.id,
                         to_warehouse_id=wh1.id, qty=50, actor_user_id=1)
    wsvc.transfer_stock(kind="feed", item_id=feed.id, from_warehouse_id=default_wh.id,
                         to_warehouse_id=wh2.id, qty=70, actor_user_id=1)

    breakdown = wsvc.warehouse_breakdown(feed, "feed")
    assert sum(e["qty"] for e in breakdown) == feed.available_qty == 200


def test_pharmacy_kind_isolated_from_feed_kind(app):
    """نفس منطق العلف بالضبط لأصناف الصيدلية — مستودعات مستقلة عن العلف
    (كائن Warehouse منفصل بحقل warehouse_type)."""
    med = make_pharmacy(name="دواء 1", available_qty=40)
    default_wh = wsvc.get_or_create_default_warehouse("pharmacy")
    sub = _named_warehouse(kind="pharmacy", name="صيدلية فرعية")
    wsvc.transfer_stock(kind="pharmacy", item_id=med.id, from_warehouse_id=default_wh.id,
                         to_warehouse_id=sub.id, qty=15, actor_user_id=1)

    breakdown = {e["warehouse"].id: e["qty"] for e in wsvc.warehouse_breakdown(med, "pharmacy")}
    assert breakdown[sub.id] == 15
    assert med.available_qty == 40


def test_existing_deduct_stock_unaffected_by_warehouse_layer(app):
    """صفر تأثير على السلوك القديم — `Feed.deduct_stock` يشتغل بلا أي
    علم عن المستودعات، والإجمالي يبقى هو المرجع الوحيد للحسابات
    القديمة (وصفات، تنبيهات نقص...)."""
    feed = make_feed(name="علف 7", available_qty=100)
    default_wh = wsvc.get_or_create_default_warehouse("feed")
    sub = _named_warehouse(name="فرعي 3")
    wsvc.transfer_stock(kind="feed", item_id=feed.id, from_warehouse_id=default_wh.id,
                         to_warehouse_id=sub.id, qty=40, actor_user_id=1)

    feed.deduct_stock(20)
    db.session.commit()

    assert feed.available_qty == 80  # 100 - 20، بدون أي علاقة بالتحويل
    breakdown = {e["warehouse"].id: e["qty"] for e in wsvc.warehouse_breakdown(feed, "feed")}
    # الخصم صار خارج طبقة المستودعات (نفس السلوك القديم تماماً) — انعكس
    # على المستودع الافتراضي المحسوب بالطرح (60 - 40)، والمستودع المسمّى ثابت.
    assert breakdown[sub.id] == 40
    assert breakdown[default_wh.id] == 40
