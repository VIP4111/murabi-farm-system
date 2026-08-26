"""نظام الرواتب الشهري العام (بند إضافي 242) — لكل عضو فريق (بخلاف
"موظف الشهر"، بند 239، مكافأة أداء لأفضل عامل بس). كل راتب = الأساسي
+ المكافأة - مجموع الخصومات (كل خصم بسبب مستقل)، بحالة مسودة قابلة
للتعديل قبل التأكيد النهائي."""
from datetime import date, timedelta

from app.extensions import db
from app.models import Payroll, PayrollDeduction, Finance
from app.core.cloud_storage_service import save_upload

ALLOWED_RECEIPT_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "pdf"}
MAX_RECEIPT_BYTES = 8 * 1024 * 1024


def top_performer_for_month(*, year: int, month: int) -> dict | None:
    """أعلى نقطة أداء موضوعية لشهر معيّن (بند إضافي 245 — دمج "موظف
    الشهر" داخل الرواتب بدل نظام منفصل بجدول/شاشة/وصل خاص به). يعيد
    استخدام `performance_service.worker_performance` مباشرة (حساب حي،
    بدون تخزين وسيط) — نفس مصدر الحقيقة المستخدم أصلاً بتقرير أداء
    الفريق، بدل تكرار منطق "من الأفضل هذا الشهر" بمكان ثانٍ."""
    from app.team.performance_service import worker_performance

    first_of_month = date(year, month, 1)
    last_of_month = (
        date(year, 12, 31) if month == 12
        else date(year, month + 1, 1) - timedelta(days=1)
    )
    rows = worker_performance(start_date=first_of_month, end_date=last_of_month)
    return rows[0] if rows else None


def get_or_create_draft(*, user, year: int, month: int) -> Payroll:
    payroll = Payroll.query.filter_by(user_id=user.id, year=year, month=month).first()
    if payroll:
        return payroll
    payroll = Payroll(
        user_id=user.id, year=year, month=month,
        base_salary=user.base_salary or 0, bonus_amount=0, status="draft",
    )
    db.session.add(payroll)
    db.session.commit()
    return payroll


def save_draft(payroll: Payroll, *, base_salary: float, bonus_amount: float,
                deductions: list[tuple[float, str]], recipient_name: str | None) -> Payroll:
    """يستبدل كل سطور الخصم الحالية بالقائمة الجديدة — أبسط من محاولة
    تتبّع تعديل/حذف صف فردي، والفورم أصلاً يرسل القائمة كاملة كل مرة
    (بند إضافي 242، زر "+ إضافة خصم" بالواجهة)."""
    if payroll.status == "confirmed":
        raise ValueError("هذا الراتب مؤكَّد مسبقاً — ما يتعدَّل.")
    payroll.base_salary = base_salary
    payroll.bonus_amount = bonus_amount
    payroll.recipient_name = (recipient_name or "").strip() or None

    PayrollDeduction.query.filter_by(payroll_id=payroll.id).delete()
    for amount, reason in deductions:
        if amount:
            db.session.add(PayrollDeduction(payroll_id=payroll.id, amount=amount, reason=reason or None))

    db.session.commit()
    return payroll


def confirm(payroll: Payroll, *, actor) -> Payroll:
    if payroll.status == "confirmed":
        return payroll
    net = payroll.net_amount
    fin = Finance(
        date=date.today(), operation_type="expense", category="راتب موظف",
        item=f"راتب {payroll.user.name} ({payroll.month}/{payroll.year})",
        amount=net,
    )
    db.session.add(fin)
    db.session.flush()

    from datetime import datetime, timezone
    payroll.status = "confirmed"
    payroll.finance_id = fin.id
    payroll.confirmed_by_id = actor.id
    payroll.confirmed_at = datetime.now(timezone.utc)
    db.session.commit()
    return payroll


def attach_signed_receipt(payroll: Payroll, file_storage) -> Payroll:
    """رفع صورة الوصل الموقَّع من العامل بعد الطباعة والتوقيع الفعلي
    (بند إضافي 242، طلبك الصريح) — خطوة منفصلة بعد التأكيد، مو جزء
    من فورم التجهيز نفسه (التوقيع يصير بعد الطباعة فعلياً)."""
    url = save_upload(file_storage, subfolder="payroll_receipts",
                       allowed_extensions=ALLOWED_RECEIPT_EXTENSIONS, max_bytes=MAX_RECEIPT_BYTES)
    if url:
        payroll.signed_receipt_file_url = url
        db.session.commit()
    return payroll
