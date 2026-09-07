"""فحص عميق — محرك دورة الإنتاج: `sell_animal` ما كانت تتحقق من
`sale_price` إطلاقاً قبل إنشاء عملية "بيع" حقيقية بسجل المالية — سعر
سالب أو صفري (خطأ كتابة) كان يُنشئ دخل "بيع" سالب/معدوم، يقلّل إجمالي
المبيعات وصافي الربح المعروضين بدل ما يعكس بيعاً حقيقياً. نفس الثغرة
كانت قابلة للوصول عبر البيع الجماعي (`bulk_service.apply_bulk_sale`)
أيضاً — سعر سالب `truthy` بايثونياً، يتجاوز فحص `if not price`."""
import pytest
from datetime import date

from app.core import cycle_engine, bulk_service
from app.extensions import db
from app.models import Finance
from tests.factories import make_animal


def _force_stage_10(animal):
    def _fake_evaluate(a):
        wf = a.workflow
        wf.current_stage = 10
        wf.stage_name = "قرار المصير"
        wf.status = "complete"
        return {
            "route": wf.route, "allowed_stage": 10, "completed_through": 10,
            "first_blocked_stage": None, "cycle_status": "complete",
            "missing_items": None, "out_of_order_count": 0,
        }
    return _fake_evaluate


def _sellable_animal(animal_no, monkeypatch):
    animal = make_animal(animal_no=animal_no, price=500)
    cycle_engine.get_or_create_workflow(animal)
    monkeypatch.setattr(cycle_engine, "evaluate", _force_stage_10(animal))
    return animal


def test_negative_sale_price_rejected(app, monkeypatch):
    animal = _sellable_animal("NEGSALE-01", monkeypatch)
    with pytest.raises(cycle_engine.CycleExitBlocked):
        cycle_engine.sell_animal(animal, sale_price=-500, actor_user_id=1)
    assert animal.status == "active"
    assert Finance.query.filter_by(related_animal_id=animal.id).count() == 0


def test_zero_sale_price_rejected(app, monkeypatch):
    animal = _sellable_animal("NEGSALE-02", monkeypatch)
    with pytest.raises(cycle_engine.CycleExitBlocked):
        cycle_engine.sell_animal(animal, sale_price=0, actor_user_id=1)
    assert animal.status == "active"


def test_bulk_sale_with_negative_price_rejected(app, monkeypatch):
    animal = _sellable_animal("NEGSALE-03", monkeypatch)
    results = bulk_service.apply_bulk_sale(
        animal_ids=[animal.id], sale_date=date.today(),
        prices_by_id={animal.id: -300}, notes=None, actor_user_id=1,
    )
    assert "مرفوض" in results[animal.id]
    db.session.refresh(animal)
    assert animal.status == "active"
    assert Finance.query.filter_by(related_animal_id=animal.id).count() == 0


def test_positive_sale_price_still_accepted(app, monkeypatch):
    animal = _sellable_animal("NEGSALE-04", monkeypatch)
    fin = cycle_engine.sell_animal(animal, sale_price=700, actor_user_id=1)
    assert fin.amount == 700
    assert animal.status == "sold"
