"""فحص عميق لقسم "الصحة/الأدوية" — `Pharmacy.deduct_stock(qty)` (نقطة
خصم المخزون الوحيدة عند تسجيل استخدام دواء بزيارة/مرض/تطعيم) ما كانت
تتحقق إن `qty` موجب. قيمة سالبة تمرّ بسهولة من فحص `qty > available`
(سالب دايماً أصغر من أي رصيد)، ثم `available_qty = available - qty`
فعلياً **يزيد** المخزون بدل ما يخصمه — ثغرة تسمح بتضخيم المخزون عبر
تسجيل "استخدام" دواء بكمية سالبة."""
import pytest

from app.extensions import db
from tests.factories import make_pharmacy


def test_negative_quantity_is_rejected_not_increasing_stock(app):
    with app.app_context():
        item = make_pharmacy(available_qty=10)
        with pytest.raises(ValueError, match="موجباً"):
            item.deduct_stock(-5)
        # ما يفترض المخزون يتغيّر إطلاقاً — العملية مرفوضة كاملة
        assert item.available_qty == 10


def test_zero_quantity_is_rejected(app):
    with app.app_context():
        item = make_pharmacy(available_qty=10)
        with pytest.raises(ValueError, match="موجباً"):
            item.deduct_stock(0)


def test_normal_positive_deduction_still_works(app):
    with app.app_context():
        item = make_pharmacy(available_qty=10)
        item.deduct_stock(3)
        db.session.commit()
        assert item.available_qty == 7
