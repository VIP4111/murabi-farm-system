"""فحص عميق مقسَّم — قسم "التقارير": `_to_local_date` (يحوّل وقت UTC
مخزَّن لتاريخ محلي، يمنع نسب نشاط لليوم الخاطئ قرب منتصف الليل) كانت
تستخدم `.astimezone()` بدون منطقة زمنية صريحة — يعتمد على توقيت نظام
التشغيل الافتراضي للسيرفر (`TZ` بالبيئة)، غير مضبوط بهذا المشروع
إطلاقاً. بيئات استضافة مُدارة زي Render تُشغّل حاوياتها بتوقيت UTC
افتراضياً، يعني هذا "الإصلاح" نفسه كان بلا أي أثر عملي بالإنتاج —
نفس مشكلة `date.today()` المُصلَحة بـ`farm_today()`، بس هنا الكود
كان يتظاهر بمعالجتها. الاختبار يفرض `TZ=UTC` على العملية صراحة (محاكاة
بيئة Render الفعلية) ويتأكد إن النتيجة صحيحة رغم ذلك."""
import os
import time
from datetime import datetime, timezone

import pytest

from app.reports.report_service import _to_local_date


@pytest.fixture()
def force_system_tz_utc():
    """يحاكي بيئة استضافة مُدارة (Render) اللي توقيت نظامها UTC —
    بغض النظر عن التوقيت الفعلي للجهاز اللي يشغّل الاختبار."""
    original = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    time.tzset()
    yield
    if original is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = original
    time.tzset()


def test_late_utc_night_maps_to_next_riyadh_day_even_when_system_tz_is_utc(force_system_tz_utc):
    # 22:30 UTC يوم 5 سبتمبر = 01:30 بتوقيت الرياض (UTC+3) يوم 6 سبتمبر —
    # صار يوم جديد فعلياً بالرياض رغم إن UTC لسا باليوم السابق.
    utc_naive = datetime(2026, 9, 5, 22, 30, 0)
    result = _to_local_date(utc_naive)
    assert result == datetime(2026, 9, 6).date()


def test_normal_daytime_utc_maps_correctly(force_system_tz_utc):
    # منتصف اليوم UTC = بعد الظهر بالرياض، نفس اليوم بالاثنين.
    utc_naive = datetime(2026, 9, 5, 10, 0, 0)
    result = _to_local_date(utc_naive)
    assert result == datetime(2026, 9, 5).date()
