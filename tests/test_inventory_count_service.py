"""بند إضافي 208 — طلبك بالنص (شرحته بمثال): "عندك شعير 40 كيلو،
أجي أحسب زاد عندي 5 كيلو، نقول هذا زايد يدخل ضمن المخزون. لو نقص عن
40 وطلع 30، نقول الهالك 10 كيلو تحسبها خسارة على المشروع، تقول قيمة
الهالك بسعر الكيس الأصلي، تضيف الخسارة على سعر الخراف [موزَّعة على
كل الرؤوس]." الاختبارات تتحقق من نفس المثال بالضبط."""
from datetime import date

from app.core import inventory_count_service as svc
from app.extensions import db
from app.models import Feed, Finance, InventoryCount
from factories import make_pharmacy, make_equipment


def _make_feed(name="شعير اختبار الجرد", available_qty=40, unit_price=2.0):
    item = Feed(name=name, unit="كجم", available_qty=available_qty, unit_price=unit_price, status="active")
    db.session.add(item)
    db.session.commit()
    return item


def test_surplus_corrects_stock_without_any_finance_row(app):
    feed = _make_feed(available_qty=40)
    rec = svc.record_count(kind="feed", item=feed, actual_qty=45, created_by_id=1)
    assert feed.available_qty == 45
    assert rec.diff_qty == 5
    assert rec.diff_value is None
    assert rec.finance_id is None
    assert Finance.query.count() == 0


def test_deficit_corrects_stock_and_records_indirect_expense_at_unit_price(app):
    feed = _make_feed(available_qty=40, unit_price=2.0)
    rec = svc.record_count(kind="feed", item=feed, actual_qty=30, created_by_id=1)
    assert feed.available_qty == 30
    assert rec.diff_qty == -10
    assert rec.diff_value == 20.0  # 10 كجم × 2 ريال

    fin = Finance.query.get(rec.finance_id)
    assert fin is not None
    assert fin.operation_type == "expense"
    assert fin.category == "هالك"
    assert fin.amount == 20.0
    assert fin.is_indirect is True


def test_exact_match_records_zero_diff_with_no_finance(app):
    feed = _make_feed(available_qty=40)
    rec = svc.record_count(kind="feed", item=feed, actual_qty=40, created_by_id=1)
    assert rec.diff_qty == 0
    assert rec.diff_value is None
    assert feed.available_qty == 40


def test_deficit_without_known_unit_price_records_zero_value_loss(app):
    feed = _make_feed(available_qty=40, unit_price=None)
    rec = svc.record_count(kind="feed", item=feed, actual_qty=35)
    assert rec.diff_value == 0.0
    fin = Finance.query.get(rec.finance_id)
    assert fin.amount == 0.0


def test_count_works_for_pharmacy_and_equipment_kinds(app):
    med = make_pharmacy(name="دواء اختبار الجرد", available_qty=20, unit_price=5.0)
    rec = svc.record_count(kind="pharmacy", item=med, actual_qty=18)
    assert rec.diff_value == 10.0

    equip = make_equipment(name="أداة اختبار الجرد", available_qty=10, unit_price=3.0)
    rec2 = svc.record_count(kind="equipment", item=equip, actual_qty=8)
    assert rec2.diff_value == 6.0


def test_record_persists_snapshot_fields(app):
    feed = _make_feed(available_qty=40, unit_price=2.0)
    rec = svc.record_count(kind="feed", item=feed, actual_qty=30, count_date=date(2026, 8, 17), note="جرد شهري")
    saved = InventoryCount.query.get(rec.id)
    assert saved.kind == "feed"
    assert saved.item_name == "شعير اختبار الجرد"
    assert saved.count_date == date(2026, 8, 17)
    assert saved.note == "جرد شهري"
