"""فحص عميق مقسَّم — قسم "العلف والمستودعات": نفس ثغرة `Pharmacy.
deduct_stock` المُصلَحة كانت منسوخة حرفياً (نفس الشيفرة، نفس التعليق
المرجعي "نفس قيد Pharmacy.deduct_stock") بـ`Feed.deduct_stock`
و`Equipment.deduct_stock` — كمية سالبة كانت تزيد المخزون بدل تنقيصه.
كمان `add_stock` بكل الثلاثة (فيهم Pharmacy) ما عندها أي فحص — كمية
سالبة هناك كانت تُنقص المخزون بدل ما تزيده (عكس اتجاه العملية
المتوقَّع من اسمها)."""
import pytest

from app.extensions import db
from app.models import Feed, Equipment


def _make_feed(qty=10):
    item = Feed(name="علف اختبار", available_qty=qty, unit="kg", status="active")
    db.session.add(item)
    db.session.commit()
    return item


def _make_equipment(qty=10):
    item = Equipment(name="معدة اختبار", available_qty=qty, status="active")
    db.session.add(item)
    db.session.commit()
    return item


def test_feed_negative_deduct_is_rejected(app):
    with app.app_context():
        item = _make_feed(10)
        with pytest.raises(ValueError, match="موجباً"):
            item.deduct_stock(-3)
        assert item.available_qty == 10


def test_feed_negative_add_is_rejected(app):
    with app.app_context():
        item = _make_feed(10)
        with pytest.raises(ValueError, match="موجباً"):
            item.add_stock(-3)
        assert item.available_qty == 10


def test_equipment_negative_deduct_is_rejected(app):
    with app.app_context():
        item = _make_equipment(10)
        with pytest.raises(ValueError, match="موجباً"):
            item.deduct_stock(-3)
        assert item.available_qty == 10


def test_equipment_negative_add_is_rejected(app):
    with app.app_context():
        item = _make_equipment(10)
        with pytest.raises(ValueError, match="موجباً"):
            item.add_stock(-3)
        assert item.available_qty == 10


def test_pharmacy_negative_add_is_rejected(app):
    from tests.factories import make_pharmacy
    with app.app_context():
        item = make_pharmacy(available_qty=10)
        with pytest.raises(ValueError, match="موجباً"):
            item.add_stock(-3)
        assert item.available_qty == 10


def test_normal_positive_operations_still_work(app):
    with app.app_context():
        feed = _make_feed(10)
        feed.deduct_stock(3)
        feed.add_stock(2)
        db.session.commit()
        assert feed.available_qty == 9

        eq = _make_equipment(10)
        eq.deduct_stock(4)
        eq.add_stock(1)
        db.session.commit()
        assert eq.available_qty == 7
