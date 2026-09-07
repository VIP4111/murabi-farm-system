"""فحص عميق — قسم الفريق والمهام: `performance_service.todays_completed_
tasks()` (أساس شاشة "المراجعة اليومية") كانت تستخدم `date.today()`
الخام (UTC) بدل `farm_today()`. قرب منتصف الليل بالسعودية، مهمة أُنجزت
فعلياً "اليوم" بتوقيت السعودية كانت تختفي من الشاشة لأن UTC لسا يعتبره
أمس."""
from datetime import datetime as dt
from zoneinfo import ZoneInfo

from app.extensions import db
from app.team import performance_service
from app.models import Task


def test_task_completed_at_riyadh_midnight_shows_up_today(app, monkeypatch, worker):
    # 00:30 بتوقيت السعودية = 21:30 UTC اليوم السابق — المهمة أُنجزت
    # فعلياً "اليوم" بتوقيت السعودية.
    fixed_riyadh = dt(2026, 9, 2, 0, 30, tzinfo=ZoneInfo("Asia/Riyadh"))
    completed_at_utc_naive = fixed_riyadh.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    task = Task(
        title="مهمة اختبار", task_type="daily_husbandry", status="done",
        assignee_id=worker.id, completed_at=completed_at_utc_naive,
    )
    db.session.add(task)
    db.session.commit()

    class _FixedDateTime(dt):
        @classmethod
        def now(cls, tz=None):
            return fixed_riyadh.astimezone(tz) if tz else fixed_riyadh

    monkeypatch.setattr("app.extensions.datetime", _FixedDateTime)

    results = performance_service.todays_completed_tasks()
    assert task.id in [t.id for t in results], (
        "المهمة المنجزة عند منتصف الليل بتوقيت السعودية ما ظهرت بـ'مهام اليوم' — "
        "إشارة إن الدالة اعتمدت يوم UTC (لسا أمس)"
    )
