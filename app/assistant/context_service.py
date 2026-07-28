"""
"عقل" المساعد الذكي (بند 25 بالمواصفة الرئيسية) — قراءة حية لبيانات
المزرعة الفعلية من قاعدة البيانات مباشرة، بدون أي نسخة/كاش منفصلة (نفس
فلسفة شاشة التنبيهات ببند 20). كل دالة هنا "قارئة" بس، وترجع بيانات خام
جاهزة لتُصاغ كجملة عربية بـ`nlu_service.py`.

**فحص الصلاحيات مو مسؤولية هذا الملف** — `nlu_service.py` يتحقق من صلاحية
المستخدم قبل ما يستدعي أي دالة هنا (نفس نمط `@require_permission` على
الشاشات العادية)، عشان المساعد ما يكشف بيانات المستخدم ما يملك صلاحيتها.
"""
from datetime import date, timedelta
from app.models import (
    Animal, Pregnancy, Disease, Vaccination, Task, Finance,
    FeedBarnPlan, Barn, Incubator, OstrichEgg,
)
from app.core import animal_filters_service, alerts_service
from app.feed.feed_service import ration_profile


def herd_summary() -> dict:
    animals = Animal.query.filter_by(status="active").all()
    ruminants = [a for a in animals if a.species == "sheep_goat"]
    ostriches = [a for a in animals if a.species == "ostrich"]
    return {
        "total_active": len(animals),
        "ruminants_total": len(ruminants),
        "ruminants_male": sum(1 for a in ruminants if a.gender == "ذكر"),
        "ruminants_female": sum(1 for a in ruminants if a.gender == "أنثى"),
        "ostrich_total": len(ostriches),
        "ostrich_male": sum(1 for a in ostriches if a.gender == "ذكر"),
        "ostrich_female": sum(1 for a in ostriches if a.gender == "أنثى"),
    }


def pregnant_summary() -> dict:
    """نفس منطق '_is_currently_pregnant' بـ animal_filters_service: آخر
    حمل مؤكد للأنثى وما فيه ولادة مسجّلة بعده."""
    pregnant = []
    for female in Animal.query.filter_by(status="active", gender="أنثى").filter(Animal.species == "sheep_goat").all():
        last_pregnancy = (
            Pregnancy.query.filter_by(female_id=female.id, confirmed=True)
            .order_by(Pregnancy.date.desc()).first()
        )
        if not last_pregnancy:
            continue
        gave_birth_since = Animal.query.filter(
            Animal.mother_id == female.id, Animal.birth_date >= last_pregnancy.date,
        ).count() > 0
        if not gave_birth_since:
            pregnant.append(female)
    near_birth = animal_filters_service.get_filtered("near_birth")
    return {
        "count": len(pregnant),
        "animal_numbers": [a.animal_no for a in pregnant[:10]],
        "near_birth_count": len(near_birth),
        "near_birth_numbers": [a.animal_no for a in near_birth[:10]],
    }


def ostrich_summary() -> dict:
    incubators = Incubator.query.filter_by(status="active").all()
    occupied = OstrichEgg.query.filter(
        OstrichEgg.incubator_id.isnot(None), OstrichEgg.hatch_result == "pending",
    ).count()
    capacity_total = sum(i.capacity or 0 for i in incubators)
    eggs_pending = OstrichEgg.query.filter_by(hatch_result="pending").count()
    eggs_hatched = OstrichEgg.query.filter_by(hatch_result="hatched").count()
    eggs_failed = OstrichEgg.query.filter_by(hatch_result="failed").count()
    return {
        "incubators_total": len(incubators),
        "incubators_occupied": min(occupied, len(incubators)) if incubators else 0,
        "capacity_total": capacity_total,
        "eggs_pending": eggs_pending,
        "eggs_hatched": eggs_hatched,
        "eggs_failed": eggs_failed,
    }


def feed_cost_summary() -> dict:
    """تكلفة العلف اليومية التقديرية = مجموع (تكلفة كيلو الوصفة × الكمية
    اليومية لكل رأس × عدد الرؤوس النشطة بالحظيرة) لكل خطة تغذية فعّالة
    حالياً (start_date <= اليوم <= end_date أو بدون end_date)."""
    today = date.today()
    plans = FeedBarnPlan.query.filter(
        FeedBarnPlan.start_date <= today,
        (FeedBarnPlan.end_date.is_(None)) | (FeedBarnPlan.end_date >= today),
    ).all()
    total_daily_cost = 0.0
    barn_breakdown = []
    for plan in plans:
        head_count = Animal.query.filter_by(barn_id=plan.barn_id, status="active").count()
        if head_count == 0:
            continue
        cost_per_kg = ration_profile(plan.ration)["cost_per_kg"]
        daily_cost = cost_per_kg * plan.daily_qty_per_animal_kg * head_count
        total_daily_cost += daily_cost
        barn_breakdown.append({
            "barn_name": plan.barn.barn_name if plan.barn else "-",
            "ration_name": plan.ration.name if plan.ration else "-",
            "head_count": head_count,
            "daily_cost": round(daily_cost, 2),
        })
    return {
        "total_daily_cost": round(total_daily_cost, 2),
        "total_monthly_estimate": round(total_daily_cost * 30, 2),
        "barn_breakdown": barn_breakdown,
        "has_active_plans": bool(barn_breakdown),
    }


def alerts_summary(limit: int = 5) -> dict:
    alerts = alerts_service.get_alerts()
    urgent = [a for a in alerts if a["urgent"]]
    return {
        "total": len(alerts),
        "urgent_total": len(urgent),
        "top": alerts[:limit],
    }


def disease_summary() -> dict:
    today = date.today()
    rows = Disease.query.filter_by(status="active").order_by(Disease.date.asc()).all()
    return {
        "count": len(rows),
        "items": [
            {
                "animal_no": d.animal.animal_no if d.animal else "-",
                "disease_name": d.disease_name,
                "days_open": (today - d.date).days,
            }
            for d in rows[:10]
        ],
    }


def vaccinations_due_summary() -> dict:
    alerts = alerts_service.get_alerts()
    vaccine_alerts = [a for a in alerts if a["category"] == "تحصين"]
    return {
        "count": len(vaccine_alerts),
        "overdue_count": sum(1 for a in vaccine_alerts if a["urgent"]),
        "items": vaccine_alerts[:10],
    }


def my_tasks_summary(user) -> dict:
    rows = (
        Task.query.filter(
            Task.assignee_id == user.id, Task.status.in_(("pending", "in_progress")),
        ).order_by(Task.due_date.asc().nullslast()).all()
    )
    locked = [t for t in rows if t.depends_on_task_id and t.depends_on and t.depends_on.status != "done"]
    return {
        "count": len(rows),
        "locked_count": len(locked),
        "items": [
            {"title": t.title, "due_date": t.due_date, "locked": t in locked}
            for t in rows[:10]
        ],
    }


def finance_summary() -> dict:
    today = date.today()
    month_start = today.replace(day=1)
    rows = Finance.query.filter(Finance.date >= month_start, Finance.is_cancelled.is_(False)).all()
    sales = sum(r.amount for r in rows if r.operation_type == "sale")
    purchases = sum(r.amount for r in rows if r.operation_type == "purchase")
    expenses = sum(r.amount for r in rows if r.operation_type == "expense")
    debt_in = sum(r.amount for r in rows if r.operation_type == "debt_in")
    debt_repaid = sum(r.amount for r in rows if r.operation_type == "debt_repayment")
    return {
        "month_name": month_start.strftime("%Y-%m"),
        "sales": sales,
        "purchases": purchases,
        "expenses": expenses,
        "net": sales - purchases - expenses,
        "debt_outstanding": debt_in - debt_repaid,
    }
