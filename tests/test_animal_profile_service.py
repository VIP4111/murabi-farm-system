"""اختبارات app/core/animal_profile_service.py — نصيب الرأس الفردي من
المصاريف غير المباشرة (بند إضافي 46، القسم ٤)."""
from datetime import date, timedelta

from app.core.animal_service import create_animal
from app.core.animal_profile_service import get_profile
from app.extensions import db
from app.models import Finance
from app.models.animal import AnimalSource
from factories import make_animal


def test_indirect_cost_share_split_evenly(app):
    # create_animal() (مو المصنع البسيط) عشان تُسجَّل حركة الشراء المالية
    # فعلياً — نفس المسار الحقيقي اللي يبني منه purchase_cost.
    a1 = create_animal(animal_no="IP-01", source=AnimalSource.PURCHASE, gender="ذكر", price=100)
    make_animal(animal_no="IP-02", price=100)
    db.session.add(Finance(date=date.today(), operation_type="expense", amount=200, is_indirect=True))
    db.session.commit()

    profile = get_profile(a1)
    assert profile["purchase_cost"] == 100
    assert profile["indirect_cost_share"] == 100
    assert profile["total_cost_estimate"] == 200  # 100 purchase + 100 indirect share


def test_direct_expense_not_counted_as_indirect_share(app):
    a1 = make_animal(animal_no="IP-03")
    db.session.add(Finance(date=date.today(), operation_type="expense", amount=500, is_indirect=False))
    db.session.commit()

    profile = get_profile(a1)
    assert profile["indirect_cost_share"] == 0


def test_indirect_expense_before_entry_date_excluded(app):
    a1 = make_animal(animal_no="IP-04")
    old_date = date.today() - timedelta(days=30)
    db.session.add(Finance(date=old_date, operation_type="expense", amount=300, is_indirect=True))
    db.session.commit()

    profile = get_profile(a1)
    assert profile["indirect_cost_share"] == 0, "expense predates the animal's entry_date/purchase_date"
