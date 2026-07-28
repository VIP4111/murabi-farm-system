"""اختبارات تنبيه نقص مخزون تحصين مجدول (بند إضافي 65) — يفحص جدولة
تقويم التحصينات (بند 63) ضمن نافذة التنبيه العامة، ويقارن الاحتياج
المتوقع (رؤوس × جرعة افتراضية) بالمخزون المتوفر."""
from datetime import date, timedelta

from app.extensions import db
from app.core.alerts_service import get_alerts
from app.models import VaccinationSchedule, FarmSettings
from factories import make_animal, make_barn, make_pharmacy

OUR_CATEGORIES = {"نقص مخزون تحصين مجدول", "تذكير تحصين مجدول"}


def _our_alerts(barn_id):
    """يتجاهل عمداً تنبيه "حظيرة بدون مسؤول" (بند 56) اللي يطلع تلقائياً
    لأي حظيرة اختبار ما لها عامل مسؤول — مو مرتبط بهذا البند."""
    return [a for a in get_alerts() if a["barn_id"] == barn_id and a["category"] in OUR_CATEGORIES]


def test_shortage_alert_appears_when_stock_insufficient(app):
    barn = make_barn(barn_no="VSA-01")
    make_animal(animal_no="VSA-01-A1", barn_id=barn.id)
    make_animal(animal_no="VSA-01-A2", barn_id=barn.id)
    vaccine = make_pharmacy(name="لقاح تنبيه 65", available_qty=1, medicine_class="vaccine")
    vaccine.default_dose_ml = 2
    db.session.add(VaccinationSchedule(
        barn_id=barn.id, pharmacy_id=vaccine.id,
        planned_date=date.today() + timedelta(days=3),
    ))
    db.session.commit()

    matching = _our_alerts(barn.id)
    assert len(matching) == 1
    assert matching[0]["category"] == "نقص مخزون تحصين مجدول"
    assert "4.00" in matching[0]["detail"]  # 2 رأس × 2 مل
    assert matching[0]["urgent"] is False  # 3 أيام متبقية، مو مستعجل بعد


def test_reminder_only_when_stock_sufficient(app):
    barn = make_barn(barn_no="VSA-02")
    make_animal(animal_no="VSA-02-A1", barn_id=barn.id)
    vaccine = make_pharmacy(name="لقاح تنبيه 65-ب", available_qty=100, medicine_class="vaccine")
    vaccine.default_dose_ml = 2
    db.session.add(VaccinationSchedule(
        barn_id=barn.id, pharmacy_id=vaccine.id,
        planned_date=date.today() + timedelta(days=3),
    ))
    db.session.commit()

    matching = _our_alerts(barn.id)
    assert len(matching) == 1
    assert matching[0]["category"] == "تذكير تحصين مجدول"
    assert matching[0]["urgent"] is False


def test_no_shortage_calc_without_default_dose_set(app):
    barn = make_barn(barn_no="VSA-03")
    make_animal(animal_no="VSA-03-A1", barn_id=barn.id)
    vaccine = make_pharmacy(name="لقاح تنبيه 65-ج", available_qty=1, medicine_class="vaccine")
    db.session.add(VaccinationSchedule(
        barn_id=barn.id, pharmacy_id=vaccine.id,
        planned_date=date.today() + timedelta(days=3),
    ))
    db.session.commit()

    matching = _our_alerts(barn.id)
    assert len(matching) == 1
    assert matching[0]["category"] == "تذكير تحصين مجدول"
    assert "جرعة افتراضية" in matching[0]["detail"]


def test_schedule_outside_alert_window_is_not_shown(app):
    fs = FarmSettings.get()
    barn = make_barn(barn_no="VSA-04")
    vaccine = make_pharmacy(name="لقاح تنبيه 65-د", available_qty=1, medicine_class="vaccine")
    db.session.add(VaccinationSchedule(
        barn_id=barn.id, pharmacy_id=vaccine.id,
        planned_date=date.today() + timedelta(days=fs.alert_before_days + 10),
    ))
    db.session.commit()

    assert _our_alerts(barn.id) == []


def test_completed_schedule_does_not_generate_alert(app):
    barn = make_barn(barn_no="VSA-05")
    vaccine = make_pharmacy(name="لقاح تنبيه 65-هـ", available_qty=1, medicine_class="vaccine")
    db.session.add(VaccinationSchedule(
        barn_id=barn.id, pharmacy_id=vaccine.id,
        planned_date=date.today() + timedelta(days=2), status="completed",
    ))
    db.session.commit()

    assert _our_alerts(barn.id) == []


def test_urgent_when_two_days_or_less_remaining(app):
    barn = make_barn(barn_no="VSA-06")
    make_animal(animal_no="VSA-06-A1", barn_id=barn.id)
    vaccine = make_pharmacy(name="لقاح تنبيه 65-و", available_qty=0, medicine_class="vaccine")
    vaccine.default_dose_ml = 2
    db.session.add(VaccinationSchedule(
        barn_id=barn.id, pharmacy_id=vaccine.id,
        planned_date=date.today() + timedelta(days=1),
    ))
    db.session.commit()

    matching = _our_alerts(barn.id)
    assert len(matching) == 1
    assert matching[0]["urgent"] is True
