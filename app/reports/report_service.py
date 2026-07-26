"""
وحدة التقارير التحليلية (بند 22 بالمواصفة الرئيسية).

كل دالة هنا تعتمد على استعلامات تجميع (aggregation) بمستوى قاعدة
البيانات (func.count/func.sum + group_by) بدل سحب كل الصفوف وتجميعها
ببايثون — حسب طلبك صراحة لضمان السرعة حتى مع نمو البيانات.

كل تقرير يرجّع قاموس فيه:
- 'kpis': أرقام ملخّصة للبطاقات العلوية.
- 'table': {'columns': [...], 'rows': [[...]]} — الجدول الرئيسي، نفس
  الشكل يُستخدم للعرض بالشاشة وللتصدير (PDF/Excel) بدون ازدواجية منطق.
- تفاصيل إضافية حسب التقرير (توزيع الأسباب، توزيع زمني...).
"""
from datetime import date, timedelta
from calendar import monthrange
from sqlalchemy import func
from app.extensions import db
from app.models import (
    Animal, Finance, CycleEvent, AuditLog, Vaccination, Disease,
    Mating, Pregnancy,
)
from app.models.animal import AnimalSource

RANGE_LABELS = {
    "today": "اليوم", "7days": "آخر 7 أيام", "month": "الشهر الحالي", "custom": "نطاق مخصص",
}


def parse_date_range(args) -> tuple[date, date, str]:
    range_key = args.get("range", "month")
    today = date.today()
    if range_key == "today":
        return today, today, range_key
    if range_key == "7days":
        return today - timedelta(days=6), today, range_key
    if range_key == "custom":
        try:
            start = date.fromisoformat(args.get("start", ""))
        except ValueError:
            start = today.replace(day=1)
        try:
            end = date.fromisoformat(args.get("end", ""))
        except ValueError:
            end = today
        if start > end:
            start, end = end, start
        return start, end, "custom"
    return today.replace(day=1), today, "month"


def _finance_agg(operation_types, start, end):
    row = (
        db.session.query(func.count(Finance.id), func.coalesce(func.sum(Finance.amount), 0.0))
        .filter(
            Finance.operation_type.in_(operation_types),
            Finance.date.between(start, end),
            Finance.is_cancelled.is_(False),
        )
        .one()
    )
    return row[0], float(row[1])


def overview_report(start: date, end: date) -> dict:
    active_count = Animal.query.filter_by(status="active").count()

    new_entries = Animal.query.filter(
        func.date(Animal.created_at) >= start, func.date(Animal.created_at) <= end,
    ).count()

    deaths_count = CycleEvent.query.filter(
        CycleEvent.event_type == "death", CycleEvent.event_date.between(start, end),
    ).count()

    births_count = Animal.query.filter(
        Animal.source == AnimalSource.BIRTH, Animal.birth_date.between(start, end),
    ).count()

    sales_count, sales_total = _finance_agg(("sale",), start, end)
    costs_count, costs_total = _finance_agg(("purchase", "expense"), start, end)

    vaccinations_count = Vaccination.query.filter(Vaccination.date.between(start, end)).count()
    open_diseases_count = Disease.query.filter_by(status="active").count()

    denom = active_count + deaths_count
    mortality_rate = round(deaths_count / denom * 100, 1) if denom else None

    kpis = [
        ("الرؤوس النشطة حالياً", active_count),
        ("رؤوس جديدة بالفترة", new_entries),
        ("ولادات بالفترة", births_count),
        ("حالات نفوق بالفترة", deaths_count),
        ("معدل النفوق التقريبي", f"{mortality_rate}%" if mortality_rate is not None else "-"),
        ("مبيعات بالفترة", f"{sales_count} ({sales_total:,.0f})"),
        ("مصروفات+مشتريات بالفترة", f"{costs_count} ({costs_total:,.0f})"),
        ("صافي الفترة", f"{sales_total - costs_total:,.0f}"),
        ("تحصينات بالفترة", vaccinations_count),
        ("أمراض مفتوحة حالياً", open_diseases_count),
    ]
    return {
        "kpis": kpis,
        "table": {
            "columns": ["المؤشر", "القيمة"],
            "rows": [[label, str(value)] for label, value in kpis],
        },
    }


def _death_reason(animal_id: int) -> str:
    audit = (
        AuditLog.query.filter_by(action="animal.death", entity_type="Animal", entity_id=animal_id)
        .order_by(AuditLog.created_at.desc()).first()
    )
    return (audit.details if audit and audit.details else None) or "غير مذكور"


def _time_bucket_label(d: date, granular: bool) -> str:
    return str(d) if granular else f"{d.year}-{d.month:02d}"


def mortality_report(start: date, end: date) -> dict:
    events = (
        CycleEvent.query.filter(CycleEvent.event_type == "death", CycleEvent.event_date.between(start, end))
        .order_by(CycleEvent.event_date.desc()).all()
    )
    granular = (end - start).days <= 60

    rows = []
    reason_counts: dict[str, int] = {}
    time_counts: dict[str, int] = {}
    for e in events:
        animal = e.animal
        reason = _death_reason(animal.id)
        age_days = (e.event_date - animal.birth_date).days if animal.birth_date else None
        rows.append([
            animal.animal_no if animal else "-", animal.gender if animal else "-",
            str(e.event_date), reason, str(age_days) if age_days is not None else "-",
        ])
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        bucket = _time_bucket_label(e.event_date, granular)
        time_counts[bucket] = time_counts.get(bucket, 0) + 1

    return {
        "kpis": [("إجمالي حالات النفوق", len(rows))],
        "table": {"columns": ["الرقم", "الجنس", "التاريخ", "السبب", "العمر (يوم)"], "rows": rows},
        "reason_breakdown": sorted(reason_counts.items(), key=lambda x: -x[1]),
        "time_distribution": sorted(time_counts.items()),
    }


def births_report(start: date, end: date) -> dict:
    births = (
        Animal.query.filter(Animal.source == AnimalSource.BIRTH, Animal.birth_date.between(start, end))
        .order_by(Animal.birth_date.desc()).all()
    )

    rows = []
    gender_counts = {"ذكر": 0, "أنثى": 0}
    litters: dict[tuple, int] = {}
    for b in births:
        mother = b.mother
        rows.append([
            b.animal_no, b.gender or "-", str(b.birth_date),
            mother.animal_no if mother else "-", str(b.weight) if b.weight else "-",
        ])
        if b.gender in gender_counts:
            gender_counts[b.gender] += 1
        key = (b.mother_id, b.birth_date)
        litters[key] = litters.get(key, 0) + 1

    litter_sizes = list(litters.values())
    avg_litter_size = round(sum(litter_sizes) / len(litter_sizes), 2) if litter_sizes else None

    matings_count = Mating.query.filter(Mating.date.between(start, end)).count()
    confirmed_count = Pregnancy.query.filter(
        Pregnancy.date.between(start, end), Pregnancy.confirmed.is_(True),
    ).count()
    success_rate = round(confirmed_count / matings_count * 100, 1) if matings_count else None

    kpis = [
        ("ولادات بالفترة", len(rows)),
        ("ذكور / إناث", f"{gender_counts['ذكر']} / {gender_counts['أنثى']}"),
        ("متوسط حجم البطن", avg_litter_size if avg_litter_size is not None else "-"),
        ("تقريعات بالفترة", matings_count),
        ("حمل مؤكد بالفترة", confirmed_count),
        ("نسبة نجاح التقريع→حمل", f"{success_rate}%" if success_rate is not None else "-"),
    ]
    return {
        "kpis": kpis,
        "table": {"columns": ["الرقم", "الجنس", "تاريخ الولادة", "الأم", "الوزن"], "rows": rows},
    }


def sales_report(start: date, end: date) -> dict:
    sale_rows = (
        Finance.query.filter(
            Finance.operation_type == "sale", Finance.date.between(start, end), Finance.is_cancelled.is_(False),
        ).order_by(Finance.date.desc()).all()
    )
    cost_rows = (
        Finance.query.filter(
            Finance.operation_type.in_(("purchase", "expense")),
            Finance.date.between(start, end), Finance.is_cancelled.is_(False),
        ).all()
    )

    sales_count, sales_total = _finance_agg(("sale",), start, end)
    costs_count, costs_total = _finance_agg(("purchase", "expense"), start, end)
    debt_in_count, debt_in_total = _finance_agg(("debt_in",), start, end)
    debt_repaid_count, debt_repaid_total = _finance_agg(("debt_repayment",), start, end)

    category_totals: dict[str, float] = {}
    for r in cost_rows:
        cat = r.category or "غير مصنّف"
        category_totals[cat] = category_totals.get(cat, 0) + r.amount

    rows = [
        [str(r.date), r.item or "-", r.related_animal.animal_no if r.related_animal else "-", f"{r.amount:,.2f}"]
        for r in sale_rows
    ]

    kpis = [
        ("عدد عمليات البيع", sales_count),
        ("إجمالي المبيعات", f"{sales_total:,.2f}"),
        ("إجمالي المشتريات+المصروفات", f"{costs_total:,.2f}"),
        ("الصافي", f"{sales_total - costs_total:,.2f}"),
        ("دعم خارجي مستلم (دين)", f"{debt_in_total:,.2f}"),
        ("سداد دين", f"{debt_repaid_total:,.2f}"),
    ]
    return {
        "kpis": kpis,
        "table": {"columns": ["التاريخ", "البند", "الحيوان", "المبلغ"], "rows": rows},
        "category_breakdown": sorted(category_totals.items(), key=lambda x: -x[1]),
    }


REPORTS = {
    "overview": ("التقرير الشامل", overview_report),
    "mortality": ("تقرير النفوق", mortality_report),
    "births": ("تقرير الولادات والإنتاج", births_report),
    "sales": ("تقرير المبيعات والمالية", sales_report),
}
