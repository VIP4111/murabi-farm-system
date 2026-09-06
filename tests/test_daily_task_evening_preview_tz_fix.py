"""مراجعة "أكواد الخلفية" — `daily_task_service.generate_daily_husbandry_
tasks()` تولّد مهام الغد مسبقاً من الساعة 6 مساءً (`EVENING_PREVIEW_HOUR`،
بند إضافي 72 بطلبك الصريح). كل من `scheduler.py` و`alerts_service.py`
كانا يمرّران `datetime.now()` الخام (وقت السيرفر، UTC على Render) بدل
وقت السعودية — الميزة كانت تشتغل متأخرة 3 ساعات كل ليلة (تبدأ فعلياً
9 مساءً بالسعودية بدل 6 مساءً). الإصلاح: `app.extensions.farm_now_naive()`
مركزية (نفس فلسفة `farm_today()`)."""
import os
import time
from datetime import datetime

import pytest

from app.extensions import farm_now_naive


@pytest.fixture()
def force_system_tz_utc():
    original = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    time.tzset()
    yield
    if original is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = original
    time.tzset()


def test_farm_now_naive_reflects_riyadh_evening_even_when_system_tz_is_utc(force_system_tz_utc, monkeypatch):
    # الساعة 3 مساءً UTC = 6 مساءً بالسعودية (UTC+3) بالضبط — لحظة بداية
    # ميزة "توليد مهام الغد مسبقاً". لو الكود يعتمد على توقيت النظام
    # (UTC هنا)، بيرجّع الساعة 3 (قبل الحد)، مو 6 (بعد الحد بالضبط).
    from zoneinfo import ZoneInfo
    fixed_riyadh = datetime(2026, 9, 6, 18, 0, tzinfo=ZoneInfo("Asia/Riyadh"))

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_riyadh.astimezone(tz) if tz else fixed_riyadh

    monkeypatch.setattr("app.extensions.datetime", _FixedDateTime)
    result = farm_now_naive()
    assert result.hour == 18
    assert result.tzinfo is None


def test_alerts_service_passes_farm_local_time_not_raw_utc(app):
    """يتأكد إن `alerts_service.get_alerts()` (نقطة الاستدعاء الفعلية
    بكل زيارة تعرض تنبيهات) يمرّر `farm_now_naive()` فعلاً لـ
    `generate_daily_husbandry_tasks` — لا `datetime.now()` الخام.
    بتثبيت `farm_now_naive()` على الساعة 6 مساءً بالسعودية بالضبط،
    مهام الغد لازم تتولّد."""
    from datetime import date, timedelta, datetime as dt
    from zoneinfo import ZoneInfo
    import app.core.alerts_service as alerts_service

    fixed_riyadh_6pm = dt(2026, 9, 6, 18, 0, tzinfo=ZoneInfo("Asia/Riyadh"))

    class _FixedDateTime(dt):
        @classmethod
        def now(cls, tz=None):
            return fixed_riyadh_6pm.astimezone(tz) if tz else fixed_riyadh_6pm

    import app.extensions as extensions_module
    original_now = extensions_module.datetime

    with app.app_context():
        extensions_module.datetime = _FixedDateTime
        try:
            alerts_service.get_alerts()
        finally:
            extensions_module.datetime = original_now

        from app.models import Task
        expected_due = date(2026, 9, 6) + timedelta(days=1)
        tomorrow_tasks = Task.query.filter_by(source_type="DailyHusbandry", due_date=expected_due).all()
        assert tomorrow_tasks, "مهام الغد ما تولّدت رغم إنها الساعة 6 مساءً بالضبط بالسعودية"
