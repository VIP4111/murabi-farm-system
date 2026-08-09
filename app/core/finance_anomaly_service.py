"""كشف الشذوذ المالي (بند إضافي 161) — طلبك الأصلي: تنبيه فوري لو
عملية بيع/شراء/مصروف جديدة سعرها غير طبيعي مقارنة بتاريخها الفعلي،
بدل ما تكتشفها بالصدفة بعد فترة.

**المنطق**: لكل عملية جديدة، نقارنها بمتوسط آخر عمليات مماثلة (نفس
`operation_type` + نفس `category`، غير الملغاة) — لو انحرفت بنسبة
كبيرة (أعلى من `ANOMALY_THRESHOLD`) عن المتوسط التاريخي، تُعتبر شاذة.
نتطلّب حد أدنى من العمليات التاريخية (`MIN_HISTORY`) قبل أي مقارنة —
أول عملية بفئة جديدة ما إلها تاريخ تُقارن فيه، فما تُعتبر شذوذاً
تلقائياً (تفادي إنذارات كاذبة عند تسجيل صنف جديد لأول مرة)."""
from app.models import Finance

MIN_HISTORY = 3
ANOMALY_THRESHOLD = 0.5  # انحراف 50% أو أكثر عن المتوسط التاريخي


def detect_anomaly(entry: Finance) -> dict | None:
    """يرجّع `None` لو ما فيه شذوذ (أو ما فيه تاريخ كافي للمقارنة)،
    وإلا يرجّع تفاصيل الانحراف."""
    if not entry.category:
        return None

    history = (
        Finance.query.filter(
            Finance.operation_type == entry.operation_type,
            Finance.category == entry.category,
            Finance.is_cancelled.is_(False),
            Finance.id != entry.id,
        ).all()
    )
    if len(history) < MIN_HISTORY:
        return None

    avg = sum(h.amount for h in history) / len(history)
    if avg <= 0:
        return None

    deviation = (entry.amount - avg) / avg
    if abs(deviation) < ANOMALY_THRESHOLD:
        return None

    return {
        "average": avg,
        "amount": entry.amount,
        "deviation_pct": round(deviation * 100),
        "direction": "أعلى" if deviation > 0 else "أقل",
    }
