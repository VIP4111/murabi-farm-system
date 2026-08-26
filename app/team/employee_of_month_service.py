"""موظف الشهر (بند إضافي 239) — طلبك: "فقعة حمرا يختارها النظام آخر
كل شهر، تتحول خضرا بعد ما صاحب الحلال يأكّد ويحدد مكافأة، وتترحل
للمحاسب كحركة مالية".

نفس فلسفة `daily_task_service`/`daily_email_report_service` بالضبط:
فحص حي عند فتح الشاشة (بدون Cron مستقل)، idempotency عبر قيد فريد
(year, month) بالجدول نفسه — مو حارس منفصل بـFarmSettings."""
from datetime import date, timedelta

from app.extensions import db
from app.models import EmployeeOfMonth, Finance


def _previous_month_range(today: date) -> tuple[date, date, int, int]:
    first_of_this_month = today.replace(day=1)
    last_of_prev_month = first_of_this_month - timedelta(days=1)
    start = last_of_prev_month.replace(day=1)
    return start, last_of_prev_month, start.year, start.month


def select_employee_of_month_if_needed() -> EmployeeOfMonth | None:
    """يُستدعى عند أي فتح لشاشة "الفريق" (نفس نقطة استدعاء بسيطة، بدون
    تعقيد Cron) — يفحص هل فيه اختيار مسجَّل للشهر السابق، ولو ماكو
    ويوجد عمال محسومة مهامهم بذلك الشهر، يختار الأعلى نقطة تلقائياً."""
    today = date.today()
    start, end, year, month = _previous_month_range(today)

    existing = EmployeeOfMonth.query.filter_by(year=year, month=month).first()
    if existing:
        return None

    from app.team.performance_service import worker_performance
    rows = worker_performance(start_date=start, end_date=end)
    if not rows:
        return None

    top = rows[0]
    record = EmployeeOfMonth(
        year=year, month=month, user_id=top["user"].id, score=top["score"],
        status="pending_confirmation",
    )
    db.session.add(record)
    db.session.commit()

    from app.core import telegram_service
    from app.models import User
    for user in User.query.filter(User.telegram_chat_id.isnot(None), User.is_active_account.is_(True)).all():
        if user.role.name == "owner":
            telegram_service.notify_user(
                user,
                f"🏆 موظف الشهر ({month}/{year}) — تم اختياره تلقائياً: {top['user'].name} "
                f"(نقطة {top['score']}%). راجعه وأكّده من شاشة الفريق لتحديد المكافأة.",
            )
    return record


def pending_count() -> int:
    return EmployeeOfMonth.query.filter_by(status="pending_confirmation").count()


def confirm(record: EmployeeOfMonth, *, actor, bonus_amount: float, recipient_name: str | None = None) -> EmployeeOfMonth:
    """تأكيد صاحب الحلال + تحديد مبلغ المكافأة — يسجّل حركة مالية
    "مصروف" فعلية باسم العامل ويحوّل حالة السجل لـ"confirmed".
    `recipient_name` اختياري (بند إضافي 240) — اسم مستلم الحوالة
    الفعلي ببلد الاستلام، لو مختلف عن العامل نفسه."""
    from datetime import datetime, timezone
    fin = Finance(
        date=date.today(), operation_type="expense", category="مكافأة موظف الشهر",
        item=f"مكافأة موظف الشهر — {record.user.name} ({record.month}/{record.year})",
        amount=bonus_amount,
    )
    db.session.add(fin)
    db.session.flush()

    record.status = "confirmed"
    record.bonus_amount = bonus_amount
    record.recipient_name = (recipient_name or "").strip() or None
    record.finance_id = fin.id
    record.confirmed_by_id = actor.id
    record.confirmed_at = datetime.now(timezone.utc)
    db.session.commit()
    return record
