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


def _generate_if_needed_today():
    """المنطق الفعلي مشترك بين الـCron (وقت 3 فجراً) وبين نقطة التدارك
    عند أول طلب باليوم (بند إضافي 89، نقطة 6). لازم تُستدعى داخل
    app_context فعّال أصلاً."""
    from app.extensions import db
    from app.models import FarmSettings
    from app.core import daily_task_service

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

    # تقرير يومي بالبريد الإلكتروني (بند إضافي 160، المرحلة ج) — نفس
    # الحارس والفلسفة تماماً، بس حارسه الخاص (last_daily_email_report_sent)
    # عشان فشل/تعطيل البريد ما يوقف توليد مهام الرعاية اليومية أبداً.
    from app.core import daily_email_report_service
    try:
        daily_email_report_service.generate_daily_email_report_if_needed()
    except Exception as e:
        # بند إضافي 219 — كان `except Exception: pass` بدون أي تسجيل،
        # عكس كل مسارات except عامة ثانية بالمشروع (llm_bridge،
        # telegram) اللي كلها تسجّل التحذير — فشل التقرير اليومي كان
        # يختفي بلا أثر إطلاقاً، حتى بسجلات السيرفر.
        from flask import current_app
        current_app.logger.warning("daily_email_report_service failed: %s", e)

    # ملخص يومي موحّد بتيليجرام (بند إضافي 238) — نفس الحارس والفلسفة،
    # قناة مستقلة عن البريد فوق (حارسها الخاص last_daily_telegram_report_sent).
    from app.core import daily_telegram_report_service
    try:
        daily_telegram_report_service.generate_daily_telegram_report_if_needed()
    except Exception as e:
        from flask import current_app
        current_app.logger.warning("daily_telegram_report_service failed: %s", e)


def _run_daily_tasks_job(app):
    with app.app_context():
        _generate_if_needed_today()


def _run_expire_stale_drafts_job(app):
    """بند إضافي 299 — تحسينك الثالث المعتمد: تنظيف دوري حقيقي للمسودات
    المعلَّقة اللي تجاوز عمرها 48 ساعة. **نفس ملاحظة Render أعلاه تنطبق
    هنا** (العملية قد تكون نايمة وقت موعد الـCron) — لهذا `assistant.
    drafts_list` تستدعي نفس دالة التنظيف بشكل كسول عند فتح الشاشة
    كخط دفاع ثانٍ، تماماً كنمط `catch_up_daily_tasks_before_request` أدناه."""
    with app.app_context():
        from app.assistant import draft_action_service
        draft_action_service.expire_stale_drafts()


def catch_up_daily_tasks_before_request():
    """بند إضافي 89، نقطة 6 (نقد ذاتي على بند 78) — Render المجاني يطفي
    العملية بعد ~15 دقيقة خمول ويشغّلها من جديد عند أول طلب وارد.
    الـCron الداخلي (BackgroundScheduler، الساعة 3 فجراً UTC) ما ينفع
    لو العملية نايمة بالضبط بتلك اللحظة — غالب الوقت على الخطة
    المجانية. هذا catch-up بسيط: كل طلب وارد يتأكد (بفحص خفيف من قاعدة
    البيانات) إن مهام اليوم تولّدت، ولو لأ يولّدها فوراً بدل ما ينتظر
    الـCron. التكلفة استعلام واحد خفيف لكل طلب، والتوليد الفعلي (المكلف
    قليلاً) يصير مرة وحدة كل يوم بس بحكم نفس حارس last_daily_tasks_auto_run
    أعلاه."""
    _generate_if_needed_today()


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
    # بند إضافي 299 — كل ساعة كافٍ تماماً لعتبة 48 ساعة (لا حاجة لدقة
    # أعلى من هذا لتنظيف مسودات معلَّقة).
    _scheduler.add_job(
        _run_expire_stale_drafts_job, "cron", minute=0,
        args=[app], id="expire_stale_draft_actions", replace_existing=True,
    )
    _scheduler.start()
    return _scheduler
