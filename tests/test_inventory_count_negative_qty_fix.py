"""فحص عميق — قسم المستودعات: `record_count` (الجرد الفعلي) ما كانت
تتحقق من `actual_qty` إطلاقاً — قيمة سالبة (خطأ كتابة بالميزان) كانت
تُخزَّن مباشرة كرصيد مخزون سالب، وتحسب "هالك" مضخَّماً بالغلط يُرحَّل
كمصروف حقيقي بسجل المالية."""
import pytest

from app.core import inventory_count_service as svc
from app.extensions import db
from app.models import Feed, Finance


def _make_feed(available_qty=40, unit_price=2.0):
    item = Feed(name="شعير اختبار سالب", unit="كجم", available_qty=available_qty,
                unit_price=unit_price, status="active")
    db.session.add(item)
    db.session.commit()
    return item


def test_negative_actual_qty_rejected(app):
    feed = _make_feed(available_qty=40)
    with pytest.raises(ValueError):
        svc.record_count(kind="feed", item=feed, actual_qty=-5, created_by_id=1)

    assert feed.available_qty == 40, "رصيد المخزون تغيّر رغم إن الكمية المُدخلة سالبة"
    assert Finance.query.count() == 0


def test_zero_actual_qty_still_accepted(app):
    feed = _make_feed(available_qty=40, unit_price=2.0)
    rec = svc.record_count(kind="feed", item=feed, actual_qty=0, created_by_id=1)
    assert feed.available_qty == 0
    assert rec.diff_qty == -40
