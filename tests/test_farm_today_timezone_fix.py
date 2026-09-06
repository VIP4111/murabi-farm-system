"""بحث "منطق الأعمال" (2026-09-06) — النظام كان يستخدم `date.today()`
بـ163 موضع، معتمداً على توقيت السيرفر (UTC على Render)، بدون أي تحويل
لتوقيت السعودية (UTC+3). النتيجة: كل ليلة، من 12:00 صباحاً لين 3:00
صباحاً بتوقيت السعودية، "تاريخ اليوم" بالسيرفر لسا اليوم اللي فات.
إصلاح محدود الأثر (قرارك الصريح): `farm_today()` مركزية، مطبَّقة بأهم
نقطتين — الجدولة اليومية وعداد أيام الحجر الصحي."""
from datetime import date, datetime, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.extensions import farm_today
from app.core.cycle_engine import _gate_quarantine
from app.models.animal import AnimalSource
from tests.factories import make_animal


def test_farm_today_returns_riyadh_date_even_when_utc_is_still_previous_day():
    """الساعة 1:00 صباحاً بتوقيت الرياض (UTC+3) = 10:00 مساءً بتوقيت UTC
    لليوم اللي قبله — لو النظام يعتمد على UTC، بيقول إنه لسا اليوم
    السابق. `farm_today()` لازم يرجّع اليوم الصحيح بتوقيت الرياض."""
    riyadh_2am = datetime(2026, 3, 15, 2, 0, tzinfo=ZoneInfo("Asia/Riyadh"))
    utc_equivalent = riyadh_2am.astimezone(timezone.utc)
    assert utc_equivalent.date() == date(2026, 3, 14)  # لسا اليوم السابق بتوقيت UTC

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return utc_equivalent.astimezone(tz) if tz else utc_equivalent

    with patch("app.extensions.datetime", _FixedDateTime):
        assert farm_today() == date(2026, 3, 15)  # لكن فعلياً صار يوم جديد بالرياض


def test_quarantine_gate_uses_riyadh_date_not_utc_date(app):
    """رأس دخل قبل يوم واحد فقط من انتهاء فترة الحجر (فترة الحجر
    الافتراضية 21 يوم) — لسا بالحجر. القياس هنا يتأكد إن
    `_gate_quarantine` يستخدم `farm_today()` (مو `date.today()`
    المستورد بأعلى الملف) لحساب الأيام."""
    from datetime import timedelta
    from app.extensions import db

    with app.app_context():
        from app.models import FarmSettings, VetVisit, Doctor
        fs = FarmSettings.get()
        entry_date = farm_today() - timedelta(days=fs.quarantine_days - 1)
        animal = make_animal(animal_no="TIP-QT-1", source=AnimalSource.PURCHASE)
        animal.purchase_date = entry_date
        animal.weight = 30
        doctor = Doctor(name="د. اختبار")
        db.session.add(doctor)
        db.session.flush()
        db.session.add(VetVisit(animal_id=animal.id, doctor_id=doctor.id, date=entry_date))
        db.session.commit()

        passed, missing = _gate_quarantine(animal, None)
        assert not passed
        assert any("فترة حجر" in m for m in missing)
