"""فحص عميق شامل — `validation_service.validate_not_future_date` كانت
تستخدم `date.today()` الخام (وقت سيرفر Render UTC) بدل `farm_today()`.
هذي الدالة المشتركة تُستدعى من عدة شاشات إدخال حقيقية (المالية، سجل
الحليب، الحيوانات...). عكس بقية إصلاحات التوقيت (حافة نادرة قرب منتصف
الليل)، هذا الخلل يتكرر **يومياً وبدون استثناء** بنافذة 3 ساعات ثابتة:
21:00-23:59 UTC = 00:00-02:59 بالسعودية اليوم التالي — أي عملية بتاريخ
"اليوم" الحقيقي بالسعودية خلال هذي النافذة كانت تُرفَض بخطأ "التاريخ
بالمستقبل" بالغلط."""
from datetime import date, datetime as dt
from zoneinfo import ZoneInfo

import pytest

from app.core import validation_service


def test_riyadh_today_not_rejected_as_future_when_utc_still_yesterday(monkeypatch):
    # 01:00 بتوقيت السعودية يوم 2 سبتمبر = 22:00 UTC يوم 1 سبتمبر —
    # المستخدم يسجّل عملية بتاريخ "اليوم" الحقيقي (2 سبتمبر بالسعودية).
    fixed_riyadh = dt(2026, 9, 2, 1, 0, tzinfo=ZoneInfo("Asia/Riyadh"))

    class _FixedDateTime(dt):
        @classmethod
        def now(cls, tz=None):
            return fixed_riyadh.astimezone(tz) if tz else fixed_riyadh

    monkeypatch.setattr("app.extensions.datetime", _FixedDateTime)

    # لو الكود القديم (date.today() الخام UTC) يشتغل، بيعتبر 2026-09-02
    # "مستقبل" لأن UTC لسا 2026-09-01 — يرفع خطأ رغم إنه تاريخ اليوم
    # الحقيقي بالسعودية.
    validation_service.validate_not_future_date(date(2026, 9, 2))


def test_actual_future_date_still_rejected(monkeypatch):
    fixed_riyadh = dt(2026, 9, 2, 1, 0, tzinfo=ZoneInfo("Asia/Riyadh"))

    class _FixedDateTime(dt):
        @classmethod
        def now(cls, tz=None):
            return fixed_riyadh.astimezone(tz) if tz else fixed_riyadh

    monkeypatch.setattr("app.extensions.datetime", _FixedDateTime)

    with pytest.raises(ValueError):
        validation_service.validate_not_future_date(date(2026, 9, 3))
