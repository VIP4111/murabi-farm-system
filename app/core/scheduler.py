"""
جدولة تلقائية حقيقية (بند إضافي 78، 2026-08-01) — أول Cron حقيقي
بالمشروع. كل "مهمة يومية"/"تنبيه" قبل هذا كان يُحسب بس لما حد يفتح
شاشة معيّنة (نمط "احسب عند الطلب" المتكرر بكل المشروع) — لو ما حد فتح
الشاشة يومين، ما فيه مهام تولّدت فعلياً لتلك الفترة. هذا يشغّل توليد
المهام اليومية مرة كل يوم تلقائياً، بغض النظر عن أي زيارة.

**نطاق متعمَّد**: التنبيهات (`alerts_service.get_alerts`) تبقى محسوبة
عند الطلب — هي أصلاً بلا حالة مخزّنة (ما فيه جدول Alert بقاعدة
البيانات)، فتحويلها لنظام مجدول حقيقي يحتاج بناء نموذج بيانات جديد
كامل (تخزين، حالة مقروء/غير مقروء) — تغيير أكبر بكثير، يستاهل بند
منفصل لو تبيه، مو تحت هذا البند.
"""
from datetime import date, datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

_scheduler = None


def _run_daily_tasks_job(app):
    from app.extensions import db
    from app.models import FarmSettings
    from app.core import daily_task_service

    with app.app_context():
        today = date.today()
        settings = FarmSettings.get()
        # حارس بسيط (مو قفل موزَّع مثالي) يمنع تكرار التوليد أكثر من
        # مرة بنفس اليوم لو أكثر من عملية worker حاولت بنفس الوقت —
        # `generate_daily_husbandry_tasks` نفسها idempotent أصلاً
        # فهذا احتياط مزدوج، مو الحارس الوحيد ضد التكرار.
        if settings.last_daily_tasks_auto_run == today:
            return
        daily_task_service.generate_daily_husbandry_tasks(now=datetime.now())
        settings.last_daily_tasks_auto_run = today
        db.session.commit()


def init_scheduler(app):
    """يُستدعى مرة وحدة من create_app. يتجاهل نفسه تماماً وقت الاختبارات
    (TESTING) عشان pytest ما يشغّل خيط خلفية حي بكل تشغيلة، وبوضع
    debug/reloader المحلي يشتغل بس بالعملية الفعلية (مو عملية المراقبة
    اللي يشغّلها Werkzeug reloader مرتين)."""
    global _scheduler
    if app.config.get("TESTING"):
        return
    import os
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return
    if _scheduler is not None:
        return

    _scheduler = BackgroundScheduler(timezone=timezone.utc)
    _scheduler.add_job(
        _run_daily_tasks_job, "cron", hour=3, minute=0,
        args=[app], id="daily_husbandry_tasks", replace_existing=True,
    )
    _scheduler.start()
    return _scheduler
