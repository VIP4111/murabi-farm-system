"""تقرير يومي تلقائي بالبريد الإلكتروني (بند إضافي 160، المرحلة ج) —
نفس فلسفة `daily_task_service`/`scheduler.py` (بند 78) بالضبط: مرة
واحدة كل يوم، عبر الـCron الداخلي مع نقطة تدارك عند أول طلب باليوم
(الخطة المجانية على Render تنام، فالـCron المجدول بالساعة 3 فجراً قد
يفوته وقت النوم).

**إعادة هيكلة (بند إضافي 303)** — طلبك المفصَّل بعد تحليلك للتقرير
القديم: الأرقام كانت متجاورة بدون سياق (رقم واحد "مهام مفتوحة/متأخرة"
يخلط مهام متأخرة فعلاً عن موعدها بمهام بدون تاريخ استحقاق أصلاً — نفس
فئة الخلط اللي خلت "124 مهمة" تبدو أخطر بكثير مما هي)، بدون تسلسل بصري
يبرز الحرج، وبدون رابط مباشر لحل أي شي. هذا الملف صار يبني نسخة نص
عادي (fallback لعملاء بريد ما يدعمون HTML) ونسخة HTML منسَّقة معاً."""
import os
from datetime import date

from app.extensions import db
from app.core import email_service


def _app_base_url() -> str:
    """نفس نمط `telegram_commands_service._new_report_link` بالضبط —
    Render يحقن `RENDER_EXTERNAL_URL` تلقائياً بالإنتاج؛ فاضي محلياً،
    فالروابط تختفي بهدوء (بدون رابط مكسور) بدل ما تكسر التقرير كله."""
    return os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")


def _task_breakdown(today) -> dict:
    """تصحيح خلط الأرقام (بند 303) — بدل رقم واحد "مفتوحة/متأخرة"
    يخلط ثلاث حالات مختلفة تماماً بخطورتها، نفصلها صراحة: متأخرة فعلاً
    عن موعدها (تحتاج إجراء اليوم)، مستحقة اليوم بالضبط، وبدون تاريخ
    استحقاق (خلفية عامة، أقل إلحاحاً)."""
    from app.models import Task
    base = Task.query.filter(Task.status.in_(["pending", "in_progress"]))
    overdue = base.filter(Task.due_date.isnot(None), Task.due_date < today).count()
    due_today = base.filter(Task.due_date == today).count()
    no_date = base.filter(Task.due_date.is_(None)).count()
    return {"overdue": overdue, "due_today": due_today, "no_date": no_date,
            "total": overdue + due_today + no_date}


def _alert_link(alert: dict, abs_fn) -> str | None:
    """رابط "حل المشكلة" المطلَق لتنبيه واحد — `alert_action_url`
    تحتاج سياق طلب فعّال حتى لبناء مسار نسبي (`url_for`)، وهذا يُستدعى
    من مهمة خلفية (APScheduler/Cron) بسياق تطبيق بس بدون طلب حقيقي."""
    from app.core.alerts_service import alert_action_url
    try:
        from flask import current_app
        with current_app.test_request_context():
            path = alert_action_url(alert)
    except Exception:
        path = None
    return abs_fn(path) if path else None


def gather_report_data() -> dict:
    """التجميع الخام المشترك بين نسخة البريد ونسخة تيليجرام (بند
    إضافي 304) — بدل ما كل قناة تعيد حساب نفس الأرقام من الصفر (خطر
    حقيقي: احتمال يفترق الاثنان لاحقاً بصمت لو تغيّر منطق أحدهما بس)،
    كلتاهما تبنيان عرضهما من نفس المصدر الوحيد هنا."""
    from app.models import Animal, Report
    from app.core.alerts_service import get_alerts

    today = date.today()
    total_animals = Animal.query.filter_by(status="active").count()
    tasks = _task_breakdown(today)
    open_statuses = ["new", "accepted", "executed_pending_review"]
    open_reports = Report.query.filter(Report.status.in_(open_statuses)).count()
    alerts = get_alerts()
    urgent_alerts = [a for a in alerts if a.get("urgent")]
    top_alerts = (urgent_alerts or alerts)[:3]
    base_url = _app_base_url()

    def abs_fn(path: str) -> str:
        return f"{base_url}{path}" if base_url else path

    return {
        "today": today, "total_animals": total_animals, "tasks": tasks,
        "open_reports": open_reports, "alerts": alerts, "urgent_alerts": urgent_alerts,
        "top_alerts": top_alerts, "base_url": base_url, "abs": abs_fn,
    }


def build_report_email() -> tuple[str, str, str]:
    """يرجّع (العنوان، نص عادي، HTML) — نفس مصادر `/تقرير_اليوم`
    بتيليجرام (بند 160 المرحلة أ) بس بصيغة أطول ومفصَّلة تناسب بريد
    إلكتروني، مع تصحيح خلط الأرقام (بند 303)."""
    d = gather_report_data()
    today, total_animals, tasks = d["today"], d["total_animals"], d["tasks"]
    open_reports, alerts, urgent_alerts, top_alerts = d["open_reports"], d["alerts"], d["urgent_alerts"], d["top_alerts"]
    _abs = d["abs"]

    def _link(a):
        return _alert_link(a, _abs)

    subject = f"📊 تقرير مراح بو علي اليومي — {today}"

    # ---- نص عادي (fallback) ----
    text_lines = [
        subject, "",
        "موجز الحالة اليومية:",
        f"🐑 إجمالي القطيع النشط: {total_animals} رأس",
        f"🚨 تنبيهات مستعجلة: {len(urgent_alerts)} من أصل {len(alerts)}",
        f"⚠️ مهام متأخرة فعلاً: {tasks['overdue']}  |  مستحقة اليوم: {tasks['due_today']}  |  بدون تاريخ: {tasks['no_date']}",
        f"📋 بلاغات مفتوحة: {open_reports}",
    ]
    if top_alerts:
        text_lines += ["", "أهم ما يحتاج إجراء اليوم:"]
        for a in top_alerts:
            link = _link(a)
            text_lines.append(f"- {a['icon']} {a['label']} — {a.get('detail', '')}" + (f" ← {link}" if link else ""))
    text_lines += [
        "", "روابط سريعة:",
        f"- كل التنبيهات ({len(alerts)}): {_abs('/alerts')}",
        f"- المهام ({tasks['total']}): {_abs('/team/tasks')}",
        f"- المساعد الذكي: {_abs('/assistant/')}",
    ]
    text_body = "\n".join(text_lines)

    # ---- HTML (بند 303: تسلسل بصري + إجراء مباشر) ----
    def _row(label, value, color=None):
        style = f"color:{color}; font-weight:700;" if color else "font-weight:700;"
        return f'<tr><td style="padding:6px 10px; color:#555;">{label}</td><td style="padding:6px 10px; {style}">{value}</td></tr>'

    summary_rows = [
        _row("🐑 إجمالي القطيع النشط", f"{total_animals} رأس"),
        _row("🚨 تنبيهات مستعجلة", f"{len(urgent_alerts)} من أصل {len(alerts)}",
             "#c0392b" if urgent_alerts else "#2e7d32"),
        _row("⏰ مهام متأخرة فعلاً", tasks["overdue"], "#c0392b" if tasks["overdue"] else "#2e7d32"),
        _row("📅 مهام مستحقة اليوم", tasks["due_today"]),
        _row("🗂️ مهام بدون تاريخ محدَّد", tasks["no_date"], "#888"),
        _row("📋 بلاغات مفتوحة", open_reports),
    ]

    alert_items_html = ""
    for a in top_alerts:
        link = _alert_link(a)
        cta = f'<a href="{link}" style="color:#fff; background:#c0392b; padding:4px 10px; border-radius:6px; text-decoration:none; font-size:12.5px; margin-inline-start:8px;">حل المشكلة ◀</a>' if link else ""
        alert_items_html += (
            f'<li style="margin-bottom:8px;"><b>{a["icon"]} {a["label"]}</b>'
            f'<div style="color:#666; font-size:13px;">{a.get("detail", "")}</div>{cta}</li>'
        )

    html_body = f"""
    <div style="font-family:Tahoma,Arial,sans-serif; direction:rtl; text-align:right; max-width:560px; margin:0 auto;">
      <h2 style="margin:0 0 14px;">📊 تقرير مراح بو علي اليومي — {today}</h2>
      <table style="width:100%; border-collapse:collapse; background:#f7f7f7; border-radius:8px; margin-bottom:18px;">
        {''.join(summary_rows)}
      </table>
      {f'<h3 style="margin:0 0 8px;">أهم ما يحتاج إجراء اليوم:</h3><ul style="padding-inline-start:18px;">{alert_items_html}</ul>' if top_alerts else ''}
      <h3 style="margin:18px 0 8px;">🔗 روابط سريعة</h3>
      <p style="line-height:2;">
        <a href="{_abs('/alerts')}" style="color:#1a5276;">عرض كل التنبيهات ({len(alerts)})</a><br>
        <a href="{_abs('/team/tasks')}" style="color:#1a5276;">مراجعة المهام ({tasks['total']})</a><br>
        <a href="{_abs('/assistant/')}" style="color:#1a5276;">فتح المساعد الذكي</a>
      </p>
    </div>
    """

    return subject, text_body, html_body


def send_daily_report_now() -> int:
    """يبعث التقرير الآن لكل مستخدم فعّال يملك بريد مسجَّل وصلاحية
    `reports.manage` (نفس نطاق إشعارات البلاغات، بند 159) — يرجّع عدد
    الرسائل اللي نجح إرسالها فعلياً."""
    from app.models import User
    subject, text_body, html_body = build_report_email()
    sent = 0
    for user in User.query.filter(User.email.isnot(None), User.is_active_account.is_(True)).all():
        if user.has_permission("reports.manage") and email_service.notify_user(user, subject, text_body, html=html_body):
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
