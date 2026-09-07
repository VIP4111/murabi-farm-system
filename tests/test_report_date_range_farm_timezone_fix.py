"""فحص عميق — شاشة التقارير: `parse_date_range` (نقطة البداية لكل
تقرير — تحدّد "اليوم"/"الشهر الحالي" الافتراضيين) كانت تستخدم
`date.today()` الخام (وقت سيرفر Render UTC) بدل `farm_today()`.

الأثر أوضح شي بأول 3 ساعات من كل شهر جديد بتوقيت السعودية (بين منتصف
الليل و3 فجراً — لسا اليوم الأخير من الشهر السابق بتوقيت UTC): تقرير
"الشهر الحالي" الافتراضي كان يعرض بيانات الشهر *السابق* بالكامل،
ونطاق "اليوم" يعرض بيانات *أمس*."""
from datetime import datetime as dt
from zoneinfo import ZoneInfo

from app.reports import report_service as svc


def test_month_default_uses_riyadh_day_not_utc_at_start_of_month(monkeypatch):
    # 00:30 بتوقيت السعودية يوم 1 سبتمبر = 21:30 UTC يوم 31 أغسطس —
    # لو الكود يعتمد UTC، "اليوم" لسا 31 أغسطس (الشهر السابق).
    fixed_riyadh = dt(2026, 9, 1, 0, 30, tzinfo=ZoneInfo("Asia/Riyadh"))

    class _FixedDateTime(dt):
        @classmethod
        def now(cls, tz=None):
            return fixed_riyadh.astimezone(tz) if tz else fixed_riyadh

    monkeypatch.setattr("app.extensions.datetime", _FixedDateTime)

    start, end, range_key = svc.parse_date_range({})
    assert range_key == "month"
    assert start.month == 9 and start.day == 1, (
        f"بداية 'الشهر الحالي' جاءت {start} — إشارة إنها اعتمدت يوم UTC (لسا أغسطس) "
        "بدل يوم السعودية (سبتمبر بدأ فعلياً)"
    )
    assert end.month == 9 and end.day == 1


def test_today_preset_uses_riyadh_day_not_utc(monkeypatch):
    fixed_riyadh = dt(2026, 9, 1, 0, 30, tzinfo=ZoneInfo("Asia/Riyadh"))

    class _FixedDateTime(dt):
        @classmethod
        def now(cls, tz=None):
            return fixed_riyadh.astimezone(tz) if tz else fixed_riyadh

    monkeypatch.setattr("app.extensions.datetime", _FixedDateTime)

    start, end, range_key = svc.parse_date_range({"range": "today"})
    assert start.day == 1 and start.month == 9
    assert end == start
