"""
تقرير "تكلفة الرأس الشهرية" (بند 18 بالمواصفة الرئيسية).

التكلفة = مجموع حركات المالية (شراء + مصروف) لكل شهر، بدون الديون
(دعم خارجي/سداد دين — مو تكلفة تشغيلية حقيقية) وبدون البيع (دخل مو تكلفة).

**تنبيه صادق موثّق بالكود**: عدد الرؤوس المستخدم بكل شهر هو العدد النشط
الحالي (لحظة توليد التقرير)، مو العدد الفعلي وقت ذاك الشهر — النظام ما
عنده تتبّع تاريخي لعدد الرؤوس بعد (يحتاج جدول snapshot شهري لو تبي دقة
أكبر للأشهر الماضية اللي تغيّر فيها القطيع كثير).
"""
from datetime import date
from calendar import monthrange
from app.models import Finance, Animal

MONTH_NAMES_AR = [
    "", "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
]


def monthly_cost_per_head(*, months: int = 12) -> list[dict]:
    today = date.today()
    head_count = Animal.query.filter_by(status="active").count()

    results = []
    year, month = today.year, today.month
    for i in range(months):
        yy, mm = year, month - i
        while mm <= 0:
            mm += 12
            yy -= 1
        start = date(yy, mm, 1)
        end = date(yy, mm, monthrange(yy, mm)[1])

        total_cost = sum(
            r.amount for r in Finance.query.filter(
                Finance.date >= start, Finance.date <= end,
                Finance.operation_type.in_(("purchase", "expense")),
                Finance.is_cancelled.is_(False),
            ).all()
        )
        results.append({
            "year": yy, "month": mm, "month_name": MONTH_NAMES_AR[mm],
            "total_cost": total_cost, "head_count": head_count,
            "cost_per_head": (total_cost / head_count) if head_count else None,
        })
    return results


def annual_cost_per_head(monthly_rows: list[dict]) -> dict:
    """إجمالي سنوي واحد (بند إضافي، 2026-07-23) — نفس منهجية التوزيع
    بالتساوي على القطيع اللي يستخدمها التقرير الشهري، بس مجموع كل
    الأشهر المعروضة بدفعة وحدة، عشان توزيع المصاريف غير المباشرة
    (إيجار/صيانة/رواتب) يبين بصورة سنوية واحدة زي ما طلبت، مو شهر
    شهر بس."""
    total_cost = sum(r["total_cost"] for r in monthly_rows)
    head_count = monthly_rows[0]["head_count"] if monthly_rows else 0
    return {
        "total_cost": total_cost, "head_count": head_count,
        "cost_per_head": (total_cost / head_count) if head_count else None,
        "months_count": len(monthly_rows),
    }
