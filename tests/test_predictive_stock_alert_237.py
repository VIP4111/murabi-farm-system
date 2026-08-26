"""بند إضافي 237 — بند 3 من خطة الأتمتة الواقعية: تنبيه مخزون تنبؤي.
قبل هذا، التنبيه يعتمد بس على حد أدنى ثابت (min_stock_qty) — صنف
باستهلاك سريع يقدر ينفد خلال أيام قليلة بدون أي تنبيه لو كميته
المتبقية لسا أعلى من الحد الأدنى المضبوط."""
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.health import health_service
from app.core import stock_alert_service
from app.models import Vaccination
from tests.factories import make_animal, make_pharmacy


def _now_minus(days):
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)


def test_pharmacy_days_until_stockout_computed_from_recent_usage(app):
    pharmacy = make_pharmacy(name="لقاح اختبار", available_qty=70)
    animal = make_animal(animal_no="STK-01")
    for i in range(5):
        v = Vaccination(animal_id=animal.id, vaccine_name="لقاح", date=_now_minus(i).date(),
                         pharmacy_id=pharmacy.id, quantity_used=10)
        v.created_at = _now_minus(i)
        db.session.add(v)
    db.session.commit()

    # 5 جرعات × 10 = 50 خلال آخر 14 يوم → معدل يومي = 50/14 ≈ 3.57
    # المتبقي 70 → أيام حتى النفاد ≈ 19.6
    days = health_service.pharmacy_days_until_stockout(pharmacy, lookback_days=14)
    assert days is not None
    assert 18 < days < 21


def test_pharmacy_days_until_stockout_none_without_usage(app):
    pharmacy = make_pharmacy(name="دواء بدون استهلاك", available_qty=50)
    assert health_service.pharmacy_days_until_stockout(pharmacy) is None


def test_predictive_alert_fires_even_above_min_stock(app, monkeypatch):
    """صنف كميته أعلى من الحد الأدنى، بس معدل استهلاكه عالي — لازم
    ينبّه على أساس التنبؤ، مو الحد الثابت."""
    from app.models import User, Role
    role = Role.query.filter_by(name="doctor").first()
    doctor = User(name="دكتور اختبار", phone="0500099237", role_id=role.id,
                  language="ar", telegram_chat_id="12345")
    doctor.set_password("pass1234")
    db.session.add(doctor)
    db.session.commit()

    pharmacy = make_pharmacy(name="دواء استهلاك سريع", available_qty=100)
    pharmacy.min_stock_qty = 10  # أقل بكثير من المتوفر — الحد الثابت وحده ما ينبّه
    db.session.commit()

    animal = make_animal(animal_no="STK-02")
    for i in range(10):
        v = Vaccination(animal_id=animal.id, vaccine_name="لقاح", date=_now_minus(i).date(),
                         pharmacy_id=pharmacy.id, quantity_used=20)
        v.created_at = _now_minus(i)
        db.session.add(v)
    db.session.commit()
    # 10 جرعات × 20 = 200 خلال 14 يوم لكن المتوفر 100 بس — معدل يومي~14.3
    # أيام حتى النفاد ≈ 7 — أقل من الافتراضي predictive_stock_alert_days=7

    sent = []
    monkeypatch.setattr(stock_alert_service.telegram_service, "notify_user",
                         lambda user, text: sent.append((user.id, text)))
    stock_alert_service.check_pharmacy_stock(pharmacy)
    assert len(sent) == 1
    assert "نقص مخزون" in sent[0][1]


def test_no_alert_when_stock_healthy_and_not_running_out(app, monkeypatch):
    from app.models import User, Role
    role = Role.query.filter_by(name="doctor").first()
    doctor = User(name="دكتور اختبار٢", phone="0500099238", role_id=role.id,
                  language="ar", telegram_chat_id="12346")
    doctor.set_password("pass1234")
    db.session.add(doctor)
    db.session.commit()

    pharmacy = make_pharmacy(name="دواء وفير", available_qty=1000)
    pharmacy.min_stock_qty = 10
    db.session.commit()

    animal = make_animal(animal_no="STK-03")
    v = Vaccination(animal_id=animal.id, vaccine_name="لقاح", date=_now_minus(1).date(),
                     pharmacy_id=pharmacy.id, quantity_used=1)
    v.created_at = _now_minus(1)
    db.session.add(v)
    db.session.commit()

    sent = []
    monkeypatch.setattr(stock_alert_service.telegram_service, "notify_user",
                         lambda user, text: sent.append((user.id, text)))
    stock_alert_service.check_pharmacy_stock(pharmacy)
    assert sent == []
