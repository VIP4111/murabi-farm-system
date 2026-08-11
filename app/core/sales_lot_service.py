"""صانع مجموعات البيع الذكي (بند إضافي 191) — يجمّع رؤوس محدَّدة
جاهزة للبيع بدفعة واحدة، ويحسب إحصائياتها الاستثمارية من بيانات فعلية
موجودة أصلاً (سعر التعادل من `animal_profile_service.get_profile`،
القيمة التقديرية من `ProductionWorkflow.estimated_value`) — صفر رقم
مخترع. الاختيار الذكي (اقرب مجموعة لهدف مالي معيّن) خوارزمية تقريبية
بسيطة (greedy) مذكورة صراحة كتقريب، مو حلاً أمثل رياضياً مضموناً."""
from app.models import Animal


def sellable_animals():
    """نفس تعريف "جاهز للبيع" المستخدَم أصلاً بالكتالوج العام (بند 185)
    — نشط بغرض "بيع" — عشان الاثنين يتطابقان دائماً."""
    return Animal.query.filter_by(status="active", purpose="بيع").order_by(Animal.animal_no).all()


def animal_lot_row(animal: Animal) -> dict:
    from app.core.animal_profile_service import get_profile, _age_label
    profile = get_profile(animal)
    estimated_value = animal.workflow.estimated_value if animal.workflow else None
    margin = round(estimated_value - profile["total_cost_estimate"], 2) if estimated_value is not None else None
    return {
        "animal": animal,
        "age_label": _age_label(animal.birth_date),
        "weight": animal.weight or 0,
        "actual_cost": profile["total_cost_estimate"],
        "estimated_value": estimated_value,
        "margin": margin,
        "open_diseases": profile["open_diseases_count"],
    }


def suggest_lot_for_target(*, target_amount: float, candidates: list[dict]) -> list[int]:
    """اختيار تقريبي (greedy، مو Knapsack محسوب بدقة) لأقرب مجموعة رؤوس
    تحقق الهدف المالي بأعلى ربحية ممكنة — يرتّب حسب الهامش تنازلياً
    ويضيف رؤوساً لين ما يوصل الهدف أو تخلص القائمة. **تقريب سريع
    مقصود**، مو خوارزمية Knapsack الأمثل رياضياً (مبرَّرة: عدد الرؤوس
    بمزرعة صغيرة/متوسطة صغير بما يكفي إن الفرق العملي بينهما ضئيل،
    والبساطة هنا أهم من الدقة الرياضية القصوى)."""
    priced = [r for r in candidates if r["estimated_value"] is not None]
    priced.sort(key=lambda r: -(r["margin"] if r["margin"] is not None else -1))
    selected_ids, total = [], 0.0
    for row in priced:
        if total >= target_amount:
            break
        selected_ids.append(row["animal"].id)
        total += row["estimated_value"]
    return selected_ids


def lot_stats(rows: list[dict]) -> dict:
    n = len(rows)
    total_weight = round(sum(r["weight"] for r in rows), 1)
    avg_weight = round(total_weight / n, 1) if n else 0
    total_actual_cost = round(sum(r["actual_cost"] for r in rows), 2)
    priced_rows = [r for r in rows if r["estimated_value"] is not None]
    total_estimated_value = round(sum(r["estimated_value"] for r in priced_rows), 2) if priced_rows else None
    projected_margin = (
        round(total_estimated_value - total_actual_cost, 2) if total_estimated_value is not None else None
    )
    return {
        "count": n,
        "total_weight": total_weight,
        "avg_weight": avg_weight,
        "total_actual_cost": total_actual_cost,
        "total_estimated_value": total_estimated_value,
        "priced_count": len(priced_rows),
        "projected_margin": projected_margin,
    }
