"""مؤشر الاستبعاد المالي (Culling Index، بند إضافي 190) — يحدد الإناث
"غير الدافعة" (نفس الفلتر الموجود أصلاً بـ`animal_filters_service`:
أنثى بالغة بدون أي ولادة خلال آخر 400 يوم) ويحسب تكلفة استمرار
الاحتفاظ بها شهرياً (علف + صحة)، مقابل قيمة إنتاجية = صفر (بحكم تعريف
"غير دافع" نفسه — ما فيه مواليد تُنسَب لها بالفترة المدروسة).

**حد صادق موثَّق**: هذا مو "قرار بيع آلي" — النظام ما يبيع ولا يعزل
أي رأس تلقائياً، بس يحسب رقماً مالياً حقيقياً (تكلفة الفرصة البديلة)
من بيانات فعلية مسجَّلة، ويترك القرار لصاحب الحلال. أنثى "غير دافعة"
قد يكون سببها مؤقتاً (تأخر تقريع، مرض مؤقت) لا يستدعي استبعاداً —
راجع دائماً السجل الطبي والتكاثري قبل أي قرار بيع فعلي."""
from datetime import date, timedelta
from app.models import VetVisit, Disease, Vaccination

HEALTH_COST_WINDOW_DAYS = 180


def _monthly_health_cost(animal_id: int) -> float:
    since = date.today() - timedelta(days=HEALTH_COST_WINDOW_DAYS)
    total = (
        sum(v.cost or 0 for v in VetVisit.query.filter(
            VetVisit.animal_id == animal_id, VetVisit.date >= since).all())
        + sum(d.treatment_cost or 0 for d in Disease.query.filter(
            Disease.animal_id == animal_id, Disease.date >= since).all())
        + sum(vc.cost or 0 for vc in Vaccination.query.filter(
            Vaccination.animal_id == animal_id, Vaccination.date >= since).all())
    )
    months = HEALTH_COST_WINDOW_DAYS / 30
    return round(total / months, 2) if months else 0.0


def culling_candidates() -> list[dict]:
    from app.core.animal_filters_service import get_filtered
    from app.core.animal_profile_service import _feed_cost_estimate

    rows = []
    for animal in get_filtered("unproductive"):
        feed = _feed_cost_estimate(animal)
        monthly_feed_cost = round((feed.get("daily_cost") or 0) * 30, 2)
        monthly_health_cost = _monthly_health_cost(animal.id)
        monthly_total_cost = round(monthly_feed_cost + monthly_health_cost, 2)
        rows.append({
            "animal": animal,
            "monthly_feed_cost": monthly_feed_cost,
            "monthly_health_cost": monthly_health_cost,
            "monthly_total_cost": monthly_total_cost,
            "feed_data_available": feed.get("available", False),
        })

    rows.sort(key=lambda r: -r["monthly_total_cost"])
    return rows
