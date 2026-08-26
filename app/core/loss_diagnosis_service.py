"""تشخيص أسباب الخسارة (بند إضافي 257، طلبك الصريح: "هل يبين لي سبب
الخسارة وطريقة حل مشكلة الخسارة") — يظهر بشاشة "المالية" لو صافي آخر
30 يوم سالب (نافذة متحركة، مستقلة عن الإجمالي الكلي منذ التأسيس —
مزرعة رابحة تاريخياً ممكن تدخل فترة خسارة حالية، وهذي بالضبط الحالة
اللي تستاهل تشخيص فوري).

**مبدأ أساسي**: صفر نصيحة عامة مختلَقة ("قلّل مصاريفك"). النظام يعرض
حقائق حقيقية من بياناتك فقط — أي بند مصروف الأكبر، وكم تغيّر عن
الفترة اللي قبلها، وأي رؤوس بهامش سالب فعلياً — أنت تقرر الحل، النظام
يوريك الحقيقة بس."""
from datetime import date, timedelta
from app.models import Finance

LOSS_DIAGNOSIS_WINDOW_DAYS = 30


def _period_totals(start: date, end: date) -> tuple[float, float, dict[str, float]]:
    """(إجمالي داخل، إجمالي خارج، تفصيل الخارج حسب البند) لفترة معيّنة."""
    rows = Finance.query.filter(
        Finance.date >= start, Finance.date <= end, Finance.is_cancelled.is_(False),
    ).all()
    total_in = sum(r.amount for r in rows if r.operation_type == "sale")
    by_category: dict[str, float] = {}
    total_out = 0.0
    for r in rows:
        if r.operation_type in ("purchase", "expense"):
            total_out += r.amount
            cat = r.category or "بدون تصنيف"
            by_category[cat] = by_category.get(cat, 0) + r.amount
    return total_in, total_out, by_category


def diagnose_recent_loss() -> dict | None:
    """يرجّع `None` لو آخر 30 يوم مو خسارة (ما فيه داعي تشخيص)، وإلا
    تفصيل البنود الأكبر + مقارنتها بالفترة السابقة + عدد الرؤوس
    بهامش سالب فعلياً (من نفس محرك نقطة التعادل، بند 253/254)."""
    today = date.today()
    cur_start = today - timedelta(days=LOSS_DIAGNOSIS_WINDOW_DAYS - 1)
    prev_start = cur_start - timedelta(days=LOSS_DIAGNOSIS_WINDOW_DAYS)
    prev_end = cur_start - timedelta(days=1)

    cur_in, cur_out, cur_by_cat = _period_totals(cur_start, today)
    net = cur_in - cur_out
    if net >= 0:
        return None

    _, _, prev_by_cat = _period_totals(prev_start, prev_end)

    categories = []
    for cat, amount in sorted(cur_by_cat.items(), key=lambda kv: -kv[1]):
        prev_amount = prev_by_cat.get(cat, 0)
        change_pct = round(((amount - prev_amount) / prev_amount) * 100) if prev_amount else None
        categories.append({
            "category": cat, "amount": round(amount, 2),
            "percent_of_total": round((amount / cur_out) * 100, 1) if cur_out else 0,
            "change_pct": change_pct,
        })

    from app.core.animal_profile_service import break_even_summary
    at_risk_count = sum(1 for r in break_even_summary() if r["at_risk"])

    return {
        "window_days": LOSS_DIAGNOSIS_WINDOW_DAYS,
        "start": cur_start, "end": today,
        "total_in": round(cur_in, 2), "total_out": round(cur_out, 2), "net": round(net, 2),
        "categories": categories,
        "at_risk_count": at_risk_count,
    }
