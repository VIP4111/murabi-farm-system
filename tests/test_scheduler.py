"""بند إضافي 78 — أول Cron حقيقي بالمشروع. الاختبارات هنا تتحقق من
منطق الوظيفة المجدولة نفسها (توليد المهام + الحارس ضد التكرار)
مباشرة، بدون تشغيل جدولة APScheduler حية (TESTING=True يوقفها أصلاً،
مطابق لسلوك create_app الفعلي)."""
from datetime import date

from app.core.scheduler import _run_daily_tasks_job, init_scheduler
from app.models import FarmSettings, Task
from app.extensions import db


def test_run_daily_tasks_job_creates_tasks_and_sets_guard(app):
    settings = FarmSettings.get()
    assert settings.last_daily_tasks_auto_run is None

    _run_daily_tasks_job(app)

    # الوظيفة تفتح app_context خاص فيها وتلتزم (commit) بداخله — لازم
    # نطرد الكاش المحلي (identity map) عشان نتأكد من القيمة المخزَّنة
    # فعلياً بقاعدة البيانات، مو من نسخة قديمة بالذاكرة.
    db.session.expire_all()
    settings = FarmSettings.get()
    assert settings.last_daily_tasks_auto_run == date.today()
    assert Task.query.filter_by(source_type="DailyHusbandry").count() > 0


def test_run_daily_tasks_job_skips_if_already_run_today(app):
    settings = FarmSettings.get()
    settings.last_daily_tasks_auto_run = date.today()
    db.session.commit()

    _run_daily_tasks_job(app)

    assert Task.query.filter_by(source_type="DailyHusbandry").count() == 0


def test_init_scheduler_does_nothing_under_testing_config(app):
    assert app.config.get("TESTING") is True
    result = init_scheduler(app)
    assert result is None
