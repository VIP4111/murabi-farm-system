"""مراجعة "أكواد الخلفية" (استكمال ثانٍ) — 4 مواضع أخيرة كانت لسا
تستخدم `date.today()` الخام (وقت سيرفر Render UTC) بدل `farm_today()`:
`daily_email_report_service.gather_report_data`/
`generate_daily_email_report_if_needed`، `daily_telegram_report_service.
generate_daily_telegram_report_if_needed`، و`telegram_commands_service.
_today_summary`.

هذي المواضع أخف خطورة من إصلاح `feeding_schedule_service` (بند سابق —
تأخير 3 ساعات يومي ثابت)، لأنها حالة حافة قرب منتصف الليل بس (مو كل
يوم)، لكن نفس الفئة بالضبط ونفس الأثر: قرب منتصف الليل بتوقيت السعودية
(اللي هو بعد الساعة 21:00 UTC)، "اليوم" حسب UTC لسا اليوم السابق —
فحارس "هل أُرسل التقرير اليوم؟" (`last_daily_*_report_sent`) يفوّت
إرسال تقرير يوم كامل، وملخص أمر تيليجرام "/تقرير_اليوم" يعرض بيانات
اليوم الخطأ (البلاغات الجديدة "اليوم" تُفلتر بتاريخ UTC القديم)."""
from datetime import datetime as dt
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.extensions import db
from app.core import daily_email_report_service, daily_telegram_report_service, telegram_commands_service
from app.models import FarmSettings


def _patch_riyadh_new_day_but_utc_still_yesterday(monkeypatch):
    """لحظة 23:30 بتوقيت السعودية (يوم جديد فعلياً بالسعودية) تقابل
    20:30 UTC فقط — أي كود يعتمد `date.today()` الخام (نظام UTC) يظن
    إنه لسا اليوم السابق."""
    fixed_riyadh = dt(2026, 9, 8, 0, 30, tzinfo=ZoneInfo("Asia/Riyadh"))

    class _FixedDateTime(dt):
        @classmethod
        def now(cls, tz=None):
            return fixed_riyadh.astimezone(tz) if tz else fixed_riyadh

    monkeypatch.setattr("app.extensions.datetime", _FixedDateTime)
    return fixed_riyadh.date()  # 2026-09-08 بالسعودية


def test_daily_email_report_guard_uses_riyadh_day_not_utc(app, owner, monkeypatch):
    owner.email = "owner@example.com"
    db.session.commit()
    riyadh_today = _patch_riyadh_new_day_but_utc_still_yesterday(monkeypatch)

    settings = FarmSettings.get()
    settings.last_daily_email_report_sent = dt(2026, 9, 7).date()  # "أمس" بالسعودية
    db.session.commit()

    with patch("app.core.email_service.send_email", return_value=True) as mock_send:
        daily_email_report_service.generate_daily_email_report_if_needed()

    # لو الكود يعتمد بالغلط على UTC، بيحسب "اليوم" = 2026-09-07 (نفس
    # آخر إرسال مسجَّل) ويعتبرها مُرسَلة أصلاً، فما يبعث شي إطلاقاً.
    mock_send.assert_called_once()
    settings = FarmSettings.get()
    assert settings.last_daily_email_report_sent == riyadh_today


def test_daily_telegram_report_guard_uses_riyadh_day_not_utc(app, owner, monkeypatch):
    owner.telegram_chat_id = "123456"
    db.session.commit()
    riyadh_today = _patch_riyadh_new_day_but_utc_still_yesterday(monkeypatch)

    settings = FarmSettings.get()
    settings.last_daily_telegram_report_sent = dt(2026, 9, 7).date()
    db.session.commit()

    with patch("app.core.telegram_service.notify_user", return_value=True) as mock_send:
        daily_telegram_report_service.generate_daily_telegram_report_if_needed()

    mock_send.assert_called_once()
    settings = FarmSettings.get()
    assert settings.last_daily_telegram_report_sent == riyadh_today


def test_telegram_today_summary_uses_riyadh_day_not_utc(app, owner, monkeypatch):
    from app.models import Report

    riyadh_today = _patch_riyadh_new_day_but_utc_still_yesterday(monkeypatch)
    report = Report(
        reporter_id=owner.id, description="اختبار توقيت البلاغات",
        status="new", created_at=dt.combine(riyadh_today, dt.min.time()),
    )
    db.session.add(report)
    db.session.commit()

    summary = telegram_commands_service._today_summary()
    # لو الكود يعتمد UTC، بيحسب "اليوم" = يوم أمس بالسعودية، فالبلاغ
    # المسجَّل بتاريخ اليوم الفعلي (بالسعودية) ما يظهر بالعدّاد.
    assert "📋 بلاغات جديدة اليوم: 1" in summary
