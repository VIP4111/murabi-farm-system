"""نظام الرواتب الشهري العام (بند إضافي 242) — لكل عضو فريق (بخلاف
"موظف الشهر"، بند 239، مكافأة أداء لأفضل عامل بس). كل راتب = الأساسي
+ المكافأة - مجموع الخصومات (كل خصم بسبب مستقل)، بحالة مسودة قابلة
للتعديل قبل التأكيد النهائي."""
import calendar
from datetime import date, timedelta

from app.extensions import db
from app.models import Payroll, PayrollDeduction, Finance, WorkerTravelPeriod
from app.core.cloud_storage_service import save_upload

ALLOWED_RECEIPT_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "pdf"}
MAX_RECEIPT_BYTES = 8 * 1024 * 1024


def is_traveling(user) -> bool:
    """هل العامل مسافر حالياً (فترة سفر مفتوحة، end_date=None)؟ —
    بند إضافي 247."""
    return WorkerTravelPeriod.query.filter_by(user_id=user.id, end_date=None).first() is not None


def start_travel(user) -> WorkerTravelPeriod:
    if is_traveling(user):
        return WorkerTravelPeriod.query.filter_by(user_id=user.id, end_date=None).first()
    period = WorkerTravelPeriod(user_id=user.id, start_date=date.today())
    db.session.add(period)
    db.session.commit()
    return period


def end_travel(user) -> WorkerTravelPeriod | None:
    period = WorkerTravelPeriod.query.filter_by(user_id=user.id, end_date=None).first()
    if period:
        period.end_date = date.today()
        db.session.commit()
    return period


def present_days_in_month(user, *, year: int, month: int) -> tuple[int, int]:
    """(أيام الحضور الفعلية، إجمالي أيام الشهر) — بند إضافي 247، طلبك
    الصريح: "النظام يعتمد رواتب العامل من تاريخ وصوله الى تاريخ اخر
    شهر... كل شهر، دايماً حسب أيام الحضور الفعلية". الحضور = أيام
    الشهر ناقص (أيام قبل تاريخ الوصول لو وقع بنفس الشهر) ناقص (أيام
    أي فترة سفر متداخلة مع الشهر — فترة مفتوحة تُحسب لين نهاية الشهر
    كحد أقصى، بما إنه لسا ما رجع)."""
    days_in_month = calendar.monthrange(year, month)[1]
    month_start = date(year, month, 1)
    month_end = date(year, month, days_in_month)

    effective_start = month_start
    if user.saudi_arrival_date and user.saudi_arrival_date > month_start:
        if user.saudi_arrival_date > month_end:
            return 0, days_in_month
        effective_start = user.saudi_arrival_date

    present = (month_end - effective_start).days + 1

    for p in WorkerTravelPeriod.query.filter_by(user_id=user.id).all():
        p_end = p.end_date or month_end
        overlap_start = max(p.start_date, effective_start)
        overlap_end = min(p_end, month_end)
        if overlap_start <= overlap_end:
            present -= (overlap_end - overlap_start).days + 1

    return max(present, 0), days_in_month


def confirmed_payrolls_touched_by_period(user_id: int, start_date: date, end_date: date | None) -> list[Payroll]:
    """رواتب مؤكَّدة (Payroll.status == confirmed) لأي شهر يتقاطع مع
    فترة سفر معيّنة — بند إضافي 250، بعد نقدك الصريح: "لو عدّلت أو
    حذفت فترة سفر لشهر راتبه متأكَّد أصلاً، ما فيه أي تنبيه". يُستخدم
    كتحذير فقط عند تعديل/حذف فترة بشاشة "سجل السفر" — الراتب المؤكَّد
    نفسه Snapshot ثابت عمداً (بند 242)، ما يتغيَّر تلقائياً، بس
    المستخدم يستاهل يعرف إنه لازم يعدّله يدوياً لو احتاج."""
    end = end_date or date.today()
    months = set()
    y, m = start_date.year, start_date.month
    while (y, m) <= (end.year, end.month):
        months.add((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    if not months:
        return []
    rows = Payroll.query.filter_by(user_id=user_id, status="confirmed").all()
    return [p for p in rows if (p.year, p.month) in months]


def prorated_salary(user, *, year: int, month: int) -> float:
    """الراتب المتناسب لشهر معيّن حسب أيام الحضور الفعلية — قيمة
    مقترحة تُستخدم كنقطة بداية للمسودة عند إنشائها، تبقى قابلة
    للتعديل اليدوي بشاشة تجهيز الراتب (نفس مبدأ المشروع: النظام
    يقترح، صاحب القرار يعدّل لو احتاج)."""
    if not user.base_salary:
        return 0.0
    present, total = present_days_in_month(user, year=year, month=month)
    if total == 0:
        return 0.0
    return round(user.base_salary * present / total, 2)


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
        base_salary=prorated_salary(user, year=year, month=month), bonus_amount=0, status="draft",
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
