"""أداة تدقيق سلامة البيانات (بند إضافي 178) — فحص حي عند فتح الشاشة
(نفس فلسفة `readiness_service.py`: عرض فقط، بدون أي تعديل تلقائي على
بياناتك — لا نصلح شي بصمت، خصوصاً لبيانات مالية أو أنساب حيوانات).

كل فحص يرجّع قائمة `{label, detail, link_endpoint, link_args}` — فاضية
لو ما فيه مشكلة. الإصلاح يبقى فعل بشري واعٍ عبر شاشة السجل نفسه، مو
هذي الأداة."""
from datetime import date
from app.models import Animal, VetVisit, Disease, Vaccination, Finance, Mating


def _orphaned_animal_refs() -> list[dict]:
    """سجلات تشير لـ`animal_id` غير موجود فعلياً بجدول الحيوانات — نظرياً
    ما يصير بسبب قيود FK، لكن SQLite ما يفرضها افتراضياً بدون
    PRAGMA صريح، فهذا فحص دفاعي حقيقي مو نظرياً بس."""
    issues = []
    valid_ids = {a.id for a in Animal.query.with_entities(Animal.id).all()}

    checks = [
        (VetVisit, "زيارة بيطرية", "health.vet_visits_list"),
        (Disease, "مرض", "health.diseases_list"),
        (Vaccination, "تحصين", "health.vaccinations_list"),
    ]
    for model, label, endpoint in checks:
        orphans = [
            row for row in model.query.with_entities(model.id, model.animal_id).all()
            if row.animal_id and row.animal_id not in valid_ids
        ]
        if orphans:
            issues.append({
                "label": f"سجلات {label} يتيمة",
                "detail": f"{len(orphans)} سجل يشير لرأس غير موجود (معرّفات: {', '.join(str(o.id) for o in orphans[:10])}{'...' if len(orphans) > 10 else ''}).",
                "link_endpoint": endpoint,
            })

    orphan_matings = [
        row for row in Mating.query.with_entities(Mating.id, Mating.female_id, Mating.male_id).all()
        if (row.female_id and row.female_id not in valid_ids) or (row.male_id and row.male_id not in valid_ids)
    ]
    if orphan_matings:
        issues.append({
            "label": "سجلات تقريع يتيمة",
            "detail": f"{len(orphan_matings)} سجل تقريع يشير لأنثى/فحل غير موجود.",
            "link_endpoint": "repro.matings_list",
        })

    orphan_finance = [
        row for row in Finance.query.with_entities(Finance.id, Finance.related_animal_id).all()
        if row.related_animal_id and row.related_animal_id not in valid_ids
    ]
    if orphan_finance:
        issues.append({
            "label": "حركات مالية يتيمة",
            "detail": f"{len(orphan_finance)} حركة مالية مرتبطة برأس غير موجود.",
            "link_endpoint": "finance.finance_list",
        })

    return issues


def _illogical_birth_dates() -> list[dict]:
    """تاريخ ولادة بالمستقبل، أو أصغر من/يساوي تاريخ ولادة أحد أبويه
    (مستحيل بيولوجياً — الأب/الأم لازم يكونوا أكبر عمراً)."""
    issues = []
    today = date.today()

    future_births = Animal.query.filter(Animal.birth_date.isnot(None), Animal.birth_date > today).all()
    if future_births:
        issues.append({
            "label": "تواريخ ولادة بالمستقبل",
            "detail": f"{len(future_births)} رأس: " + "، ".join(a.animal_no for a in future_births[:10]),
            "link_endpoint": "core.animals_list",
        })

    younger_than_parent = []
    animals_with_birth_date = Animal.query.filter(Animal.birth_date.isnot(None)).all()

    for a in animals_with_birth_date:
        if a.mother and a.mother.birth_date and a.mother.birth_date >= a.birth_date:
            younger_than_parent.append(a)
        elif a.father and a.father.birth_date and a.father.birth_date >= a.birth_date:
            younger_than_parent.append(a)
    if younger_than_parent:
        issues.append({
            "label": "تاريخ ولادة أصغر من (أو يساوي) تاريخ ولادة أحد الأبوين",
            "detail": f"{len(younger_than_parent)} رأس: " + "، ".join(a.animal_no for a in younger_than_parent[:10]),
            "link_endpoint": "core.animals_list",
        })

    return issues


def _finance_missing_category() -> list[dict]:
    """مصروف بدون فئة أو بدون أي وصف (صنف/وصف) — يصعّب تصنيف التقارير
    لاحقاً ويضعف دقة تقارير التكلفة."""
    issues = []
    no_category = Finance.query.filter(
        Finance.is_cancelled.is_(False), Finance.operation_type == "expense",
        db_none_or_empty(Finance.category),
    ).all()
    if no_category:
        issues.append({
            "label": "مصاريف بدون فئة",
            "detail": f"{len(no_category)} حركة مصروف بدون فئة مسجَّلة — يأثّر على دقة تقارير التكلفة المصنَّفة.",
            "link_endpoint": "finance.finance_list",
        })

    no_description = Finance.query.filter(
        Finance.is_cancelled.is_(False),
        db_none_or_empty(Finance.item), db_none_or_empty(Finance.description),
    ).all()
    if no_description:
        issues.append({
            "label": "حركات مالية بدون صنف ولا وصف",
            "detail": f"{len(no_description)} حركة بدون أي تفصيل — يصعّب مراجعتها لاحقاً.",
            "link_endpoint": "finance.finance_list",
        })
    return issues


def db_none_or_empty(column):
    from sqlalchemy import or_
    return or_(column.is_(None), column == "")


def run_full_audit() -> list[dict]:
    issues = []
    issues.extend(_orphaned_animal_refs())
    issues.extend(_illogical_birth_dates())
    issues.extend(_finance_missing_category())
    return issues
