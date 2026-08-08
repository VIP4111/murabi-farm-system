"""أوامر تيليجرام تفاعلية (المرحلة أ من بند إضافي 160) — كل عضو يكتب
أمر بمحادثة البوت ويرد عليه فوراً بمعلومة جاهزة (مو صفحة كاملة)، حسب
دوره: أوامر عامة لكل الأعضاء، وأوامر خاصة لصاحب الحلال/الدكتور/العامل.

مصدر الاستقبال: Webhook حقيقي (`/telegram/webhook`)، لا استطلاع دوري
(polling) — أرخص وأسرع، ومناسب لأن التطبيق أصلاً سيرفر ويب دائم التشغيل.
التحقق من هوية المرسل: `telegram_chat_id` المسجَّل بحساب المستخدم، نفس
آلية الإشعارات الصادرة (بند 157) بالضبط — بدون تسجيل مسبق، البوت يرد
برسالة توضيحية بس، صفر كسر أو وصول غير مصرَّح لبيانات."""
from datetime import date

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
        telegram_service.send_message(
            chat_id, "هذا الحساب على تيليجرام غير مرتبط بأي مستخدم بالنظام."
        )
        return

    command = text.split()[0].lstrip("/")
    telegram_service.send_message(chat_id, _dispatch(command, user))


def _dispatch(command: str, user) -> str:
    role = user.role.name if user.role else None

    if command == "مهامي":
        return _my_tasks(user)

    if command in ("تنبيهات", "بلاغات", "تقرير_اليوم"):
        if role != "owner":
            return "هذا الأمر خاص بصاحب الحلال فقط."
        if command == "تنبيهات":
            return _alerts_summary()
        if command == "بلاغات":
            return _open_reports_summary()
        return _today_summary()

    if command in ("بلاغاتي", "طوارئ"):
        if role != "doctor":
            return "هذا الأمر خاص بالدكتور فقط."
        if command == "بلاغاتي":
            return _my_reports_summary(user)
        return _isolation_summary()

    if command == "بلاغي_الجديد":
        if role != "worker":
            return "هذا الأمر خاص بالعامل فقط."
        return _new_report_link()

    return (
        "الأمر غير معروف. الأوامر المتاحة: /مهامي"
        + {
            "owner": "، /تنبيهات، /بلاغات، /تقرير_اليوم",
            "doctor": "، /بلاغاتي، /طوارئ",
            "worker": "، /بلاغي_الجديد",
        }.get(role, "")
    )


def _my_tasks(user) -> str:
    from app.models import Task
    tasks = (
        Task.query.filter_by(assignee_id=user.id)
        .filter(Task.status.in_(["pending", "in_progress"]))
        .order_by(Task.due_date.asc())
        .all()
    )
    if not tasks:
        return "لا توجد مهام مفتوحة عليك حالياً. 👍"
    lines = [f"- {t.title}" + (f" (موعدها {t.due_date})" if t.due_date else "") for t in tasks[:10]]
    return f"✅ مهامك المفتوحة ({len(tasks)}):\n" + "\n".join(lines)


def _alerts_summary() -> str:
    from app.core.alerts_service import get_alerts
    alerts = get_alerts()
    if not alerts:
        return "لا توجد تنبيهات حالياً. ✅"
    urgent = [a for a in alerts if a.get("urgent")]
    shown = urgent[:8] if urgent else alerts[:8]
    lines = [f"{a['icon']} {a['label']} — {a['detail']}" for a in shown]
    header = f"🔔 عدد التنبيهات: {len(alerts)} (منها {len(urgent)} مستعجل)\n\n"
    return header + "\n".join(lines)


def _open_reports_summary() -> str:
    from app.models import Report
    open_statuses = ["new", "accepted", "executed_pending_review"]
    reports = Report.query.filter(Report.status.in_(open_statuses)).order_by(Report.id.desc()).all()
    if not reports:
        return "لا توجد بلاغات مفتوحة حالياً. ✅"
    labels = {"new": "جديد", "accepted": "مقبول", "executed_pending_review": "بانتظار المراجعة"}
    newest = reports[0]
    return (
        f"📋 بلاغات مفتوحة: {len(reports)}\n"
        f"أحدثها (#{newest.id}, {labels.get(newest.status, newest.status)}): {newest.description[:150]}"
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
        f"📊 تقرير اليوم ({today}):\n"
        f"🐑 إجمالي الرؤوس النشطة: {total_animals}\n"
        f"✅ مهام مفتوحة/متأخرة: {tasks_today}\n"
        f"📋 بلاغات جديدة اليوم: {new_reports_today}\n"
        f"🔔 تنبيهات مستعجلة: {urgent_alerts}"
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
        return "لا توجد بلاغات مستلمة عليك حالياً. 👍"
    labels = {"accepted": "مقبول", "executed_pending_review": "بانتظار المراجعة"}
    lines = [f"- #{r.id} ({labels.get(r.status, r.status)}): {r.description[:80]}" for r in reports[:8]]
    return f"📋 بلاغاتك المستلمة ({len(reports)}):\n" + "\n".join(lines)


def _isolation_summary() -> str:
    from app.models import Animal, Barn
    isolated = (
        Animal.query.join(Barn, Animal.barn_id == Barn.id)
        .filter(Barn.barn_type == "عزل", Animal.status == "active")
        .count()
    )
    if not isolated:
        return "لا توجد حالات معزولة حالياً. ✅"
    return f"🚨 عدد الرؤوس المعزولة حالياً: {isolated}"


def _new_report_link() -> str:
    import os
    base = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
    if not base:
        return "افتح التطبيق ← البلاغات ← بلاغ جديد."
    return f"📋 رفع بلاغ جديد:\n{base}/team/reports/new"
