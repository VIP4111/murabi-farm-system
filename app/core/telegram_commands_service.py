"""أوامر تيليجرام تفاعلية — المرحلة أ (قراءة سريعة) + المرحلة ب (تحكم
فعلي: قبول/إغلاق بلاغ، توزيع مهمة، تأكيد تنفيذ) من بند إضافي 160. كل
عضو يكتب أمر بمحادثة البوت ويرد عليه فوراً بنتيجة الإجراء، حسب دوره.

مصدر الاستقبال: Webhook حقيقي (`/telegram/webhook`)، لا استطلاع دوري
(polling) — أرخص وأسرع، ومناسب لأن التطبيق أصلاً سيرفر ويب دائم التشغيل.
التحقق من هوية المرسل: `telegram_chat_id` المسجَّل بحساب المستخدم، نفس
آلية الإشعارات الصادرة (بند 157) بالضبط — بدون تسجيل مسبق، البوت يرد
برسالة توضيحية بس، صفر كسر أو وصول غير مصرَّح لبيانات.

أوامر المرحلة ب تستخدم دوال `report_service`/`task_service` الموجودة
أصلاً بالضبط (نفس قواعد الصلاحية والحالة اللي تطبَّق من التطبيق) —
البوت واجهة جديدة بس، مو مسار موازٍ بقواعد مختلفة."""
from datetime import date

from flask_babel import gettext as _, force_locale

from app.core import telegram_service


def handle_update(update: dict) -> None:
    from app.models.telegram_update import already_processed
    if already_processed(update.get("update_id")):
        return

    message = update.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()
    if chat_id is None or not text:
        return

    from app.models import User
    user = User.query.filter_by(telegram_chat_id=str(chat_id)).first()
    if not user or not user.is_active_account:
        # ما فيه مستخدم معروف بعد، فما نعرف لغته — رسالة ثنائية اللغة
        # عمداً هذي الحالة الوحيدة (بقية الردود تتبع لغة المستخدم فعلياً
        # عبر `force_locale` تحت).
        telegram_service.send_message(
            chat_id,
            "هذا الحساب على تيليجرام غير مرتبط بأي مستخدم بالنظام."
            "\nThis Telegram account isn't linked to any system user.",
        )
        return

    # بند إضافي (2026-08-31) — نفس فجوة التقرير اليومي بالضبط: هذا
    # مسار Webhook حقيقي (له سياق طلب)، لكن `current_user` غير مسجَّل
    # دخول (الهوية تُحدَّد بمطابقة `telegram_chat_id`، لا جلسة تسجيل
    # دخول)، فـ`select_locale` يرجع عربي افتراضياً بغض النظر عن لغة
    # المستخدم المطابق فعلياً. `force_locale` هنا يضمن كل نصوص `_dispatch`
    # تُترجَم بلغة صاحب الحساب الحقيقية.
    with force_locale(user.language or "ar"):
        reply = _dispatch(text, user)
    telegram_service.send_message(chat_id, reply)


def _dispatch(text: str, user) -> str:
    role = user.role.name if user.role else None

    if text.strip() == "تم":
        return _mark_done(user)

    parts = text.split()
    command = parts[0].lstrip("/")
    args = parts[1:]

    if command == "مهامي":
        return _my_tasks(user)

    if command in ("تنبيهات", "بلاغات", "تقرير_اليوم"):
        if role != "owner":
            return _("هذا الأمر خاص بصاحب الحلال فقط.")
        if command == "تنبيهات":
            return _alerts_summary()
        if command == "بلاغات":
            return _open_reports_summary()
        return _today_summary()

    if command in ("بلاغاتي", "طوارئ"):
        # بند إضافي 294 — طلبك الصريح "نعم" على إصلاح فجوة "المزارع"
        # ببوت تيليجرام: الفحص كان باسم الدور الحرفي "doctor"، فأي دور
        # مخصَّص (زي "المزارع" مستنسخ من عامل، أو دور بيطري مخصَّص لاحقاً)
        # يُرفض حتى لو صلاحياته الفعلية تسمح له. صار يفحص الصلاحية
        # الحقيقية (`health.view`) بدل اسم الدور — نفس مبدأ الصلاحيات
        # المطبَّق بكل مكان ثانٍ بالنظام.
        if not user.has_permission("health.view"):
            return _("هذا الأمر يحتاج صلاحية عرض السجل الصحي.")
        if command == "بلاغاتي":
            return _my_reports_summary(user)
        return _isolation_summary()

    if command == "بلاغي_الجديد":
        # بند إضافي 294 — نفس المبدأ: صلاحية `reports.submit` بدل اسم
        # الدور الحرفي "worker".
        if not user.has_permission("reports.submit"):
            return _("هذا الأمر يحتاج صلاحية رفع بلاغ.")
        return _new_report_link()

    if command == "قبول":
        return _accept_report_cmd(user, args)

    if command == "إغلاق":
        return _close_report_cmd(user, args)

    if command == "مهمة":
        return _assign_task_cmd(user, args)

    # بند إضافي 294 — نص المساعدة نفسه صار حسب الصلاحية الفعلية بدل
    # اسم الدور، عشان دور مخصَّص (زي "المزارع") يشوف الأوامر المتاحة
    # له فعلياً، مو قائمة فاضية لأن اسمه ما يطابق "worker" حرفياً.
    extra = ""
    if role == "owner":
        extra += "، /تنبيهات، /بلاغات، /تقرير_اليوم"
    if user.has_permission("health.view"):
        extra += "، /بلاغاتي، /طوارئ"
    if user.has_permission("reports.manage"):
        extra += "، /قبول رقم_البلاغ، /إغلاق رقم_البلاغ"
    if user.has_permission("tasks.assign_any"):
        extra += "، /مهمة جوال_العضو نص_المهمة"
    if user.has_permission("reports.submit"):
        extra += "، /بلاغي_الجديد"
    # ملاحظة (2026-08-31): أسماء الأوامر نفسها (/تنبيهات، /مهامي...)
    # تبقى عربية عمداً — هذي أوامر حرفية يكتبها المستخدم بمحادثة
    # تيليجرام، مو نص عرض، وترجمتها تعني دعم أسماء أوامر إنجليزية
    # موازية (قرار تصميم أكبر، غير مطلوب حالياً). النص المحيط بس هو
    # المترجَم.
    return _("الأمر غير معروف. الأوامر المتاحة: /مهامي، تم") + extra


def _my_tasks(user) -> str:
    from app.models import Task
    tasks = (
        Task.query.filter_by(assignee_id=user.id)
        .filter(Task.status.in_(["pending", "in_progress"]))
        .order_by(Task.due_date.asc())
        .all()
    )
    if not tasks:
        return _("لا توجد مهام مفتوحة عليك حالياً. 👍")
    lines = [f"- {t.title}" + (_(" (موعدها %(d)s)", d=t.due_date) if t.due_date else "") for t in tasks[:10]]
    return _("✅ مهامك المفتوحة (%(n)s):", n=len(tasks)) + "\n" + "\n".join(lines)


def _alerts_summary() -> str:
    from app.core.alerts_service import get_alerts
    alerts = get_alerts()
    if not alerts:
        return _("لا توجد تنبيهات حالياً. ✅")
    urgent = [a for a in alerts if a.get("urgent")]
    shown = urgent[:8] if urgent else alerts[:8]
    lines = [f"{a['icon']} {a['label']} — {a['detail']}" for a in shown]
    header = _("🔔 عدد التنبيهات: %(total)s (منها %(urgent)s مستعجل)", total=len(alerts), urgent=len(urgent))
    return header + "\n\n" + "\n".join(lines)


def _open_reports_summary() -> str:
    from app.models import Report
    open_statuses = ["new", "accepted", "executed_pending_review"]
    reports = Report.query.filter(Report.status.in_(open_statuses)).order_by(Report.id.desc()).all()
    if not reports:
        return _("لا توجد بلاغات مفتوحة حالياً. ✅")
    labels = {"new": _("جديد"), "accepted": _("مقبول"), "executed_pending_review": _("بانتظار المراجعة")}
    newest = reports[0]
    return (
        _("📋 بلاغات مفتوحة: %(n)s", n=len(reports)) + "\n" +
        _("أحدثها (#%(id)s, %(status)s): %(desc)s",
          id=newest.id, status=labels.get(newest.status, newest.status), desc=newest.description[:150])
    )


def _today_summary() -> str:
    from app.models import Animal, Task, Report
    today = date.today()
    total_animals = Animal.query.filter_by(status="active").count()
    tasks_today = (
        Task.query.filter(Task.status.in_(["pending", "in_progress"]))
        .filter((Task.due_date.is_(None)) | (Task.due_date <= today))
        .count()
    )
    new_reports_today = Report.query.filter(
        Report.status == "new", db_date_eq(Report.created_at, today)
    ).count()
    from app.core.alerts_service import get_alerts
    urgent_alerts = sum(1 for a in get_alerts() if a.get("urgent"))
    return (
        _("📊 تقرير اليوم (%(date)s):", date=today) + "\n" +
        _("🐑 إجمالي الرؤوس النشطة: %(n)s", n=total_animals) + "\n" +
        _("✅ مهام مفتوحة/متأخرة: %(n)s", n=tasks_today) + "\n" +
        _("📋 بلاغات جديدة اليوم: %(n)s", n=new_reports_today) + "\n" +
        _("🔔 تنبيهات مستعجلة: %(n)s", n=urgent_alerts)
    )


def db_date_eq(column, day):
    from sqlalchemy import func
    return func.date(column) == day


def _my_reports_summary(user) -> str:
    from app.models import Report
    open_statuses = ["accepted", "executed_pending_review"]
    reports = (
        Report.query.filter_by(manager_id=user.id)
        .filter(Report.status.in_(open_statuses))
        .order_by(Report.id.desc())
        .all()
    )
    if not reports:
        return _("لا توجد بلاغات مستلمة عليك حالياً. 👍")
    labels = {"accepted": _("مقبول"), "executed_pending_review": _("بانتظار المراجعة")}
    lines = [f"- #{r.id} ({labels.get(r.status, r.status)}): {r.description[:80]}" for r in reports[:8]]
    return _("📋 بلاغاتك المستلمة (%(n)s):", n=len(reports)) + "\n" + "\n".join(lines)


def _isolation_summary() -> str:
    from app.models import Animal, Barn
    isolated = (
        Animal.query.join(Barn, Animal.barn_id == Barn.id)
        .filter(Barn.barn_type == "عزل", Animal.status == "active")
        .count()
    )
    if not isolated:
        return _("لا توجد حالات معزولة حالياً. ✅")
    return _("🚨 عدد الرؤوس المعزولة حالياً: %(n)s", n=isolated)


def _new_report_link() -> str:
    import os
    base = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
    if not base:
        return _("افتح التطبيق ← البلاغات ← بلاغ جديد.")
    return _("📋 رفع بلاغ جديد:") + f"\n{base}/team/reports/new"


def _get_report_by_id(report_id_text):
    from app.models import Report
    if not report_id_text.isdigit():
        return None
    return Report.query.get(int(report_id_text))


def _accept_report_cmd(user, args) -> str:
    if not user.has_permission("reports.manage"):
        return _("هذا الأمر يحتاج صلاحية إدارة البلاغات.")
    if not args:
        return _("الصيغة: /قبول رقم_البلاغ")
    report = _get_report_by_id(args[0])
    if not report:
        return _("لا يوجد بلاغ برقم %(id)s.", id=args[0])
    from app.team import report_service as svc
    try:
        svc.accept_report(report, actor=user)
        return _("✅ تم قبول البلاغ #%(id)s.", id=report.id)
    except (svc.ReportPermissionError, svc.ReportStateError) as e:
        return f"⚠️ {e}"


def _close_report_cmd(user, args) -> str:
    if not args:
        return _("الصيغة: /إغلاق رقم_البلاغ")
    report = _get_report_by_id(args[0])
    if not report:
        return _("لا يوجد بلاغ برقم %(id)s.", id=args[0])
    from app.team import report_service as svc
    try:
        svc.close_report(report, actor=user)
        return _("✅ تم إغلاق البلاغ #%(id)s.", id=report.id)
    except (svc.ReportPermissionError, svc.ReportStateError) as e:
        return f"⚠️ {e}"


def _assign_task_cmd(user, args) -> str:
    if not user.has_permission("tasks.assign_any"):
        return _("هذا الأمر يحتاج صلاحية توزيع المهام.")
    if len(args) < 2:
        return _("الصيغة: /مهمة جوال_العضو نص_المهمة")
    phone, title = args[0], " ".join(args[1:])
    from app.models import User
    target = User.query.filter_by(phone=phone).first()
    if not target or not target.is_active_account:
        return _("لا يوجد عضو فعّال بجوال %(phone)s.", phone=phone)
    from app.team import task_service as svc
    svc.assign_task(actor=user, title=title, assignee_id=target.id)
    return _("✅ تم توزيع مهمة على %(name)s:", name=target.name) + f"\n{title}"


def _mark_done(user) -> str:
    from app.models import Task, Report
    task = (
        Task.query.filter_by(assignee_id=user.id)
        .filter(Task.status.in_(["pending", "in_progress"]))
        .order_by(Task.id.desc())
        .first()
    )
    if task:
        from app.team import task_service as tsvc
        try:
            tsvc.complete_task(task, actor=user, note=_("تم الإنجاز عبر تيليجرام"))
            return _("✅ تم إنجاز المهمة: %(title)s", title=task.title)
        except (tsvc.TaskStateError, tsvc.TaskPermissionError) as e:
            return f"⚠️ {e}"

    report = (
        Report.query.filter_by(executor_id=user.id, status="accepted")
        .order_by(Report.id.desc())
        .first()
    )
    if report:
        from app.team import report_service as rsvc
        try:
            rsvc.executor_mark_done(report, actor=user, note=_("تم الإنجاز عبر تيليجرام"))
            return _("✅ تم تسجيل تنفيذ البلاغ #%(id)s.", id=report.id)
        except (rsvc.ReportStateError, rsvc.ReportPermissionError) as e:
            return f"⚠️ {e}"

    return _("ما فيه مهمة أو بلاغ مفتوح عليك حالياً.")
