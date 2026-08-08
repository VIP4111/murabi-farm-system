"""تقرير يومي تلقائي بالبريد الإلكتروني (بند إضافي 160، المرحلة ج) —
نفس فلسفة `daily_task_service`/`scheduler.py` (بند 78) بالضبط: مرة
واحدة كل يوم، عبر الـCron الداخلي مع نقطة تدارك عند أول طلب باليوم
(الخطة المجانية على Render تنام، فالـCron المجدول بالساعة 3 فجراً قد
يفوته وقت النوم)."""
from datetime import date

from app.extensions import db
from app.core import email_service


def build_report_email() -> tuple[str, str]:
    """يرجّع (العنوان، النص) — نفس مصادر `/تقرير_اليوم` بتيليجرام
    (بند 160 المرحلة أ) بس بصيغة أطول تناسب بريد إلكتروني."""
    from app.models import Animal, Task, Report
    from app.core.alerts_service import get_alerts

    today = date.today()
    total_animals = Animal.query.filter_by(status="active").count()
    open_tasks = (
        Task.query.filter(Task.status.in_(["pending", "in_progress"]))
        .filter((Task.due_date.is_(None)) | (Task.due_date <= today))
        .count()
    )
    open_statuses = ["new", "accepted", "executed_pending_review"]
    open_reports = Report.query.filter(Report.status.in_(open_statuses)).count()
    alerts = get_alerts()
    urgent_alerts = [a for a in alerts if a.get("urgent")]

    lines = [
        f"📊 تقرير مراح بو علي اليومي — {today}",
        "",
        f"🐑 إجمالي الرؤوس النشطة: {total_animals}",
        f"✅ مهام مفتوحة/متأخرة: {open_tasks}",
        f"📋 بلاغات مفتوحة: {open_reports}",
        f"🔔 تنبيهات: {len(alerts)} (منها {len(urgent_alerts)} مستعجل)",
    ]
    if urgent_alerts:
        lines.append("")
        lines.append("أهم التنبيهات المستعجلة:")
        for a in urgent_alerts[:10]:
            lines.append(f"- {a['icon']} {a['label']} — {a['detail']}")

    subject = f"تقرير مراح بو علي اليومي — {today}"
    return subject, "\n".join(lines)


def send_daily_report_now() -> int:
    """يبعث التقرير الآن لكل مستخدم فعّال يملك بريد مسجَّل وصلاحية
    `reports.manage` (نفس نطاق إشعارات البلاغات، بند 159) — يرجّع عدد
    الرسائل اللي نجح إرسالها فعلياً."""
    from app.models import User
    subject, body = build_report_email()
    sent = 0
    for user in User.query.filter(User.email.isnot(None), User.is_active_account.is_(True)).all():
        if user.has_permission("reports.manage") and email_service.notify_user(user, subject, body):
            sent += 1
    return sent


def generate_daily_email_report_if_needed() -> None:
    from app.models import FarmSettings
    today = date.today()
    settings = FarmSettings.get()
    if settings.last_daily_email_report_sent == today:
        return
    send_daily_report_now()
    settings.last_daily_email_report_sent = today
    db.session.commit()
