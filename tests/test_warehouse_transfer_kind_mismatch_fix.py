"""فحص عميق — قسم المستودعات: `transfer_stock` ما كانت تتحقق إن مستودع
الوجهة من نفس نوع الصنف المُحوَّل (أو "مختلط") — دفاع بعمق ناقص:
الشاشة تفلتر القائمة المعروضة، لكن الدالة نفسها تقبل أي `warehouse_id`
بدون فحص، فطلب مباشر للسيرفر (أو خطأ بالفورم) كان يقدر ينشئ صف
`FeedWarehouseStock` مربوط بمستودع من نوع "صيدلية" — بيانات متناقضة."""
import pytest

from app.core import warehouse_service as wsvc
from app.extensions import db
from app.models import Warehouse
from factories import make_feed


def test_transfer_to_mismatched_kind_warehouse_rejected(app):
    feed = make_feed(name="علف اختبار", available_qty=50)
    default_wh = wsvc.get_or_create_default_warehouse("feed")
    pharmacy_wh = Warehouse(name="صيدلية فرعية", warehouse_type="pharmacy", is_default=False)
    db.session.add(pharmacy_wh)
    db.session.commit()

    with pytest.raises(ValueError):
        wsvc.transfer_stock(
            kind="feed", item_id=feed.id, from_warehouse_id=default_wh.id,
            to_warehouse_id=pharmacy_wh.id, qty=10, actor_user_id=1,
        )

    breakdown = {e["warehouse"].id: e["qty"] for e in wsvc.warehouse_breakdown(feed, "feed")}
    assert pharmacy_wh.id not in breakdown, "انحفظ صف مستودع علف بمستودع من نوع مختلف"
    assert breakdown[default_wh.id] == 50  # ما تغيّر شي


def test_transfer_to_mixed_kind_warehouse_still_allowed(app):
    feed = make_feed(name="علف اختبار ب", available_qty=50)
    default_wh = wsvc.get_or_create_default_warehouse("feed")
    mixed_wh = Warehouse(name="مستودع مختلط", warehouse_type="mixed", is_default=False)
    db.session.add(mixed_wh)
    db.session.commit()

    wsvc.transfer_stock(
        kind="feed", item_id=feed.id, from_warehouse_id=default_wh.id,
        to_warehouse_id=mixed_wh.id, qty=10, actor_user_id=1,
    )

    breakdown = {e["warehouse"].id: e["qty"] for e in wsvc.warehouse_breakdown(feed, "feed")}
    assert breakdown[mixed_wh.id] == 10
