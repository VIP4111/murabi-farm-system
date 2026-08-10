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
from datetime import date, timedelta, timezone
from calendar import monthrange
from sqlalchemy import func
from flask_babel import lazy_gettext as _l
from app.extensions import db
from app.models import (
    Animal, Finance, CycleEvent, AuditLog, Vaccination, Disease,
    Mating, Pregnancy, Task, VetVisit, AnimalWeight, MilkRecord, Report,
    Feed, FeedMovement, Pharmacy,
)
from app.models.animal import AnimalSource

RANGE_LABELS = {
    "today": _l("اليوم"), "7days": _l("آخر 7 أيام"), "month": _l("الشهر الحالي"), "custom": _l("نطاق مخصص"),
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


def _to_local_date(dt) -> date:
    """أعمدة completed_at/failed_at/created_at تُخزَّن بلا tzinfo لكنها
    فعلياً وقت UTC (راجع _now() بكل الموديلات) بينما start/end هنا تواريخ
    محلية (date.today()). لو خادم Flask بتوقيت أمام UTC (مثلاً +3)، أول
    ساعات بعد منتصف الليل المحلي: date.today() صار "بكرة" بينما completed_at
    لسه "اليوم" بتوقيت UTC — يعيد بناء التاريخ المحلي الصحيح بدل مقارنة
    تاريخ UTC مباشرة بتاريخ محلي."""
    return dt.replace(tzinfo=timezone.utc).astimezone().date()


def _utc_datetime_widened(column, start: date, end: date):
    """فلتر SQL أولي موسّع بيوم بكل جهة (يغطي أي فرق توقيت ممكن) لعمود
    UTC مقابل نطاق تاريخ محلي — التحقق الدقيق يصير بعدها ببايثون عبر
    _to_local_date، بدل الاعتماد على func.date() مباشرة اللي يقارن
    تاريخ UTC الخام بتاريخ محلي ويفوّت سجلات قرب منتصف الليل."""
    return func.date(column).between(start - timedelta(days=1), end + timedelta(days=1))


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

    new_entries = sum(
        1 for a in Animal.query.filter(_utc_datetime_widened(Animal.created_at, start, end)).all()
        if a.created_at and start <= _to_local_date(a.created_at) <= end
    )

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
        (_l("الرؤوس النشطة حالياً"), active_count),
        (_l("رؤوس جديدة بالفترة"), new_entries),
        (_l("ولادات بالفترة"), births_count),
        (_l("حالات نفوق بالفترة"), deaths_count),
        (_l("معدل النفوق التقريبي"), f"{mortality_rate}%" if mortality_rate is not None else "-"),
        (_l("مبيعات بالفترة"), f"{sales_count} ({sales_total:,.0f})"),
        (_l("مصروفات+مشتريات بالفترة"), f"{costs_count} ({costs_total:,.0f})"),
        (_l("صافي الفترة"), f"{sales_total - costs_total:,.0f}"),
        (_l("تحصينات بالفترة"), vaccinations_count),
        (_l("أمراض مفتوحة حالياً"), open_diseases_count),
    ]
    return {
        "kpis": kpis,
        "table": {
            "columns": [_l("المؤشر"), _l("القيمة")],
            "rows": [[str(label), str(value)] for label, value in kpis],
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
        "kpis": [(_l("إجمالي حالات النفوق"), len(rows))],
        "table": {"columns": [_l("الرقم"), _l("الجنس"), _l("التاريخ"), _l("السبب"), _l("العمر (يوم)")], "rows": rows},
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
        (_l("ولادات بالفترة"), len(rows)),
        (_l("ذكور / إناث"), f"{gender_counts['ذكر']} / {gender_counts['أنثى']}"),
        (_l("متوسط حجم البطن"), avg_litter_size if avg_litter_size is not None else "-"),
        (_l("تقريعات بالفترة"), matings_count),
        (_l("حمل مؤكد بالفترة"), confirmed_count),
        (_l("نسبة نجاح التقريع→حمل"), f"{success_rate}%" if success_rate is not None else "-"),
    ]
    return {
        "kpis": kpis,
        "table": {"columns": [_l("الرقم"), _l("الجنس"), _l("تاريخ الولادة"), _l("الأم"), _l("الوزن")], "rows": rows},
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
        (_l("عدد عمليات البيع"), sales_count),
        (_l("إجمالي المبيعات"), f"{sales_total:,.2f}"),
        (_l("إجمالي المشتريات+المصروفات"), f"{costs_total:,.2f}"),
        (_l("الصافي"), f"{sales_total - costs_total:,.2f}"),
        (_l("دعم خارجي مستلم (دين)"), f"{debt_in_total:,.2f}"),
        (_l("سداد دين"), f"{debt_repaid_total:,.2f}"),
    ]
    return {
        "kpis": kpis,
        "table": {"columns": [_l("التاريخ"), _l("البند"), _l("الحيوان"), _l("المبلغ")], "rows": rows},
        "category_breakdown": sorted(category_totals.items(), key=lambda x: -x[1]),
    }


def purchases_report(start: date, end: date) -> dict:
    """تقرير المشتريات (بند إضافي 154) — طلبك الصريح: نفس بنية تقرير
    المبيعات بالضبط (قائمة عمليات + إجماليات + تصنيف + تصدير)، بس
    لعمليات الشراء/المصروف، مع رابط الفاتورة/الملف المرفق (`invoice_file_url`
    بند 75) داخل نفس التقرير — قبل هذا البند كانت هذي البيانات موجودة
    بس مدمجة جوا "تقرير المبيعات والمالية" بدون تفصيل عملياتي مستقل."""
    cost_rows = (
        Finance.query.filter(
            Finance.operation_type.in_(("purchase", "expense")),
            Finance.date.between(start, end), Finance.is_cancelled.is_(False),
        ).order_by(Finance.date.desc()).all()
    )

    costs_count, costs_total = _finance_agg(("purchase", "expense"), start, end)
    purchase_count, purchase_total = _finance_agg(("purchase",), start, end)
    expense_count, expense_total = _finance_agg(("expense",), start, end)

    category_totals: dict[str, float] = {}
    for r in cost_rows:
        cat = r.category or "غير مصنّف"
        category_totals[cat] = category_totals.get(cat, 0) + r.amount

    rows = [
        [str(r.date), r.item or "-", r.related_animal.animal_no if r.related_animal else "-",
         f"{r.amount:,.2f}", r.invoice_file_url or "-"]
        for r in cost_rows
    ]

    kpis = [
        (_l("عدد عمليات الشراء/المصروف"), costs_count),
        (_l("إجمالي المشتريات+المصروفات"), f"{costs_total:,.2f}"),
        (_l("عدد عمليات الشراء"), purchase_count),
        (_l("إجمالي الشراء"), f"{purchase_total:,.2f}"),
        (_l("عدد المصروفات"), expense_count),
        (_l("إجمالي المصروفات"), f"{expense_total:,.2f}"),
    ]
    return {
        "kpis": kpis,
        "table": {"columns": [_l("التاريخ"), _l("البند"), _l("الحيوان"), _l("المبلغ"), _l("الفاتورة المرفقة")], "rows": rows},
        "category_breakdown": sorted(category_totals.items(), key=lambda x: -x[1]),
    }


def _activity_row(dt, category, title, animal_no, details):
    return [str(dt), category, title, animal_no or "-", details or "-"]


def activity_report(start: date, end: date) -> dict:
    """تقرير إنجاز اليوم (بند إضافي 55.2) — فكرة أساسها كود "مقاني"، لكن
    بدل تكرار سجل نشاط جديد (النظام أصلاً فيه جداول موثّقة لكل عملية)،
    يجمع من الجداول الفعلية الموجودة نفسها لنفس النطاق الزمني المشترك مع
    بقية التقارير — بدون أي جدول أو ازدواجية منطق جديدة."""
    items = []

    for t in Task.query.filter(
        Task.status.in_(("done", "failed")),
        db.or_(
            db.and_(Task.completed_at.isnot(None), _utc_datetime_widened(Task.completed_at, start, end)),
            db.and_(Task.failed_at.isnot(None), _utc_datetime_widened(Task.failed_at, start, end)),
        ),
    ).all():
        animal_no = t.animal.animal_no if t.animal else ""
        if t.status == "done":
            when = _to_local_date(t.completed_at) if t.completed_at else start
            if not (start <= when <= end):
                continue
            detail = t.completion_note or ("مباشرها: " + t.accepted_by.name if t.accepted_by else "-")
            items.append((when, _activity_row(when, "مهمة مكتملة", t.title, animal_no, detail)))
        else:
            when = _to_local_date(t.failed_at) if t.failed_at else start
            if not (start <= when <= end):
                continue
            detail = f"{t.failure_reason or ''} — {t.completion_note or ''}".strip(" —")
            items.append((when, _activity_row(when, "مهمة متعذّرة", t.title, animal_no, detail)))

    for d in Disease.query.filter(Disease.date.between(start, end)).all():
        animal_no = d.animal.animal_no if d.animal else ""
        items.append((d.date, _activity_row(d.date, "مرض", d.disease_name, animal_no, d.severity)))

    for v in Vaccination.query.filter(Vaccination.date.between(start, end)).all():
        animal_no = v.animal.animal_no if v.animal else ""
        items.append((v.date, _activity_row(v.date, "تحصين", v.vaccine_name, animal_no, "")))

    for vv in VetVisit.query.filter(VetVisit.date.between(start, end)).all():
        animal_no = vv.animal.animal_no if vv.animal else ""
        items.append((vv.date, _activity_row(vv.date, "زيارة بيطرية", vv.diagnosis or "-", animal_no, "")))

    for w in AnimalWeight.query.filter(AnimalWeight.date.between(start, end)).all():
        animal_no = w.animal.animal_no if w.animal else ""
        items.append((w.date, _activity_row(w.date, "وزن", f"{w.weight:g} كجم", animal_no, w.notes)))

    for m in MilkRecord.query.filter(MilkRecord.date.between(start, end)).all():
        animal_no = m.animal.animal_no if m.animal else ""
        items.append((m.date, _activity_row(
            m.date, "حليب", f"{m.quantity_liters:g} لتر ({m.session})", animal_no, m.notes)))

    for f in Finance.query.filter(Finance.date.between(start, end), Finance.is_cancelled.is_(False)).all():
        animal_no = f.related_animal.animal_no if f.related_animal else ""
        items.append((f.date, _activity_row(f.date, "مالية", f.item or f.operation_type, animal_no,
                                             f"{f.amount:,.2f}")))

    for r in Report.query.filter(_utc_datetime_widened(Report.created_at, start, end)).all():
        when = _to_local_date(r.created_at) if r.created_at else start
        if not (start <= when <= end):
            continue
        animal_no = r.animal.animal_no if r.animal else ""
        items.append((when, _activity_row(when, "بلاغ", r.report_type or "-", animal_no, r.status)))

    items.sort(key=lambda x: x[0], reverse=True)
    rows = [row for _, row in items]

    by_category: dict[str, int] = {}
    for _, row in items:
        by_category[row[1]] = by_category.get(row[1], 0) + 1

    kpis = [(cat, count) for cat, count in sorted(by_category.items(), key=lambda x: -x[1])]
    kpis = kpis or [(_l("لا يوجد نشاط بهذي الفترة"), 0)]

    return {
        "kpis": kpis,
        "table": {"columns": [_l("التاريخ"), _l("الفئة"), _l("العنوان"), _l("الحيوان"), _l("التفاصيل")], "rows": rows},
    }


def purchase_request_report(start: date, end: date) -> dict:
    """تقرير طلب الشراء (بند إضافي 95) — بناءً على طلبك الصريح: الاحتياج
    يُحسب من الاستهلاك الفعلي الحقيقي بالفترة المختارة (مو تخمين حسب
    عدد الرؤوس)، نفس فلسفة "الاستهلاك الفعلي أذكى" اللي اخترتها. العلف
    يُحسب من حركات `FeedMovement` الصادرة (نفس الجدول اللي يسجّله توزيع
    العلف الفعلي على الحظائر أصلاً)، والدواء من مجموع `quantity_used`
    بسجلات الزيارات/الأمراض/التطعيمات لنفس الفترة — كلها بيانات حقيقية
    مسجَّلة أصلاً بالنظام، بدون أي جدول جديد.

    المعادلة لكل صنف: معدل الاستهلاك اليومي (المستهلك ÷ عدد أيام الفترة)
    × 30 يوم = الاحتياج المتوقع للشهر القادم. لو (الاحتياج المتوقع +
    الحد الأدنى المطلوب بالمخزون) أكبر من المخزون الحالي، يظهر الصنف
    بالتقرير بالكمية المقترح شراؤها. أصناف ما تحتاج شراء (المخزون كافٍ)
    عمداً ما تظهر — التقرير غرضه قائمة شراء عملية، مو جرد كامل."""
    days = max((end - start).days + 1, 1)
    rows = []

    feed_consumed = dict(
        db.session.query(FeedMovement.feed_id, func.coalesce(func.sum(FeedMovement.quantity), 0.0))
        .filter(FeedMovement.movement_type == "out", func.date(FeedMovement.created_at).between(start, end))
        .group_by(FeedMovement.feed_id).all()
    )
    # اقتراح الأرخص لتغطية النقص (بند إضافي 156) — طلبك الصريح: لو عندك
    # أكثر من صنف علف بديل ببعض (نفس "التصنيف" ونفس "الوحدة")، النظام
    # يجمع نقص كل الأصناف البديلة ببعض ويقترح تغطيته من الأرخص سعراً
    # بينهم بدل ما يقترح شراء كل صنف لحاله بغض النظر عن السعر. الأصناف
    # اللي ما تشارك تصنيفاً مع صنف ثانٍ، أو تصنيفها فاضي، أو ما فيها
    # سعر وحدة مسجَّل تبقى تُعامَل فردياً زي قبل — صفر تغيير سلوك لهم.
    feeds_by_category: dict[str, list] = {}
    for feed in Feed.query.filter_by(status="active").all():
        if feed.category:
            feeds_by_category.setdefault(feed.category, []).append(feed)

    substitutable_feed_ids: set[int] = set()

    for category, group in feeds_by_category.items():
        priced = [f for f in group if f.unit_price]
        if len(group) < 2 or len(priced) < 1:
            continue
        units = {f.unit or "-" for f in group}
        if len(units) > 1:
            continue  # وحدات مختلفة — ما نقدر نجمعها بأمان
        total_consumed = sum(feed_consumed.get(f.id, 0.0) for f in group)
        total_current = sum(f.available_qty or 0 for f in group)
        total_min_stock = sum(f.min_stock_qty or 0 for f in group)
        projected_30d = (total_consumed / days) * 30
        total_shortfall = max(0.0, projected_30d + total_min_stock - total_current)
        if total_shortfall <= 0:
            continue
        cheapest = min(priced, key=lambda f: f.unit_price)
        others = [f.name for f in group if f.id != cheapest.id]
        rows.append([
            "علف", f'{cheapest.name} — الأرخص لتغطية نقص تصنيف "{category}" (بديل عن: {", ".join(others)})',
            f"{total_consumed:g}", f"{projected_30d:.1f}", f"{total_current:g}",
            f"{total_shortfall:.1f}", cheapest.unit or "-",
        ])
        substitutable_feed_ids.update(f.id for f in group)

    for feed in Feed.query.filter_by(status="active").all():
        if feed.id in substitutable_feed_ids:
            continue
        consumed = feed_consumed.get(feed.id, 0.0)
        projected_30d = (consumed / days) * 30
        current = feed.available_qty or 0
        suggested = max(0.0, projected_30d + (feed.min_stock_qty or 0) - current)
        if suggested > 0:
            rows.append(["علف", feed.name, f"{consumed:g}", f"{projected_30d:.1f}",
                         f"{current:g}", f"{suggested:.1f}", feed.unit or "-"])

    def _pharmacy_usage(model):
        return (db.session.query(model.pharmacy_id, func.coalesce(func.sum(model.quantity_used), 0.0))
                .filter(model.pharmacy_id.isnot(None), model.date.between(start, end))
                .group_by(model.pharmacy_id).all())

    med_consumed: dict[int, float] = {}
    for pid, qty in _pharmacy_usage(VetVisit) + _pharmacy_usage(Disease) + _pharmacy_usage(Vaccination):
        med_consumed[pid] = med_consumed.get(pid, 0.0) + (qty or 0.0)
    for p in Pharmacy.query.filter_by(status="active").all():
        consumed = med_consumed.get(p.id, 0.0)
        projected_30d = (consumed / days) * 30
        current = p.available_qty or 0
        suggested = max(0.0, projected_30d + (p.min_stock_qty or 0) - current)
        if suggested > 0:
            rows.append(["دواء", p.name, f"{consumed:g}", f"{projected_30d:.1f}",
                         f"{current:g}", f"{suggested:.1f}", p.unit or "-"])

    active_animals = Animal.query.filter_by(status="active").count()
    kpis = [
        (_l("عدد الرؤوس النشطة"), active_animals),
        (_l("عدد الأصناف المطلوب شراؤها"), len(rows)),
        (_l("فترة قياس الاستهلاك (أيام)"), days),
    ]
    return {
        "kpis": kpis,
        "table": {
            "columns": [_l("النوع"), _l("الصنف"), _l("المستهلك بالفترة"), _l("الاحتياج المتوقع (30 يوم)"),
                        _l("المخزون الحالي"), _l("الكمية المقترح شراؤها"), _l("الوحدة")],
            "rows": rows,
        },
    }


REPORTS = {
    "overview": (_l("التقرير الشامل"), overview_report),
    "mortality": (_l("تقرير النفوق"), mortality_report),
    "births": (_l("تقرير الولادات والإنتاج"), births_report),
    "sales": (_l("تقرير المبيعات والمالية"), sales_report),
    "purchases": (_l("تقرير المشتريات"), purchases_report),
    "activity": (_l("تقرير إنجاز اليوم"), activity_report),
    "purchase_request": (_l("تقرير طلب الشراء"), purchase_request_report),
}
