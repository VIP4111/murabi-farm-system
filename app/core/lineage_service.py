"""محرك الوقاية من القرابة الوراثية (بند إضافي 175) — يفحص درجة صلة
القرابة بين ذكر وأنثى قبل تسجيل تقريع فعلي، ويعرض تحذيراً حرجاً لو
كانت الدرجة أولى (أب/ابنة، أم/ابن، إخوة أشقاء كاملين) أو ثانية (إخوة
من طرف واحد، جد/حفيدة، عم أو خال/ابنة الأخ أو الأخت).

**حدود صريحة**: الفحص يعتمد حصراً على `Animal.mother_id`/`father_id`
المسجَّلين فعلياً بالنظام — لو الأنساب غير مسجَّلة (شراء بدون بيانات
أبوين، أو فحل خارجي بدون رقم مسجَّل عبر `male_note`)، ما فيه شي يُفحص
أصلاً، والنظام ما يخترع علاقة قرابة غير موثّقة. هذا تحذير إحصائي مبني
على الأنساب المعروفة، مو فحصاً وراثياً مخبرياً فعلياً."""
from flask_babel import lazy_gettext as _l
from app.models import Animal

# معامل القرابة التقريبي (Wright's coefficient of relationship) —
# قيم قياسية بعلم الوراثة الكمية، مو تقديراً مننا. النصوص هنا مُغلَّفة
# بـ`_l()` (نفس نمط FILTERS/BULK_ACTIONS بالمشروع) عشان تترجم فعلياً
# بالواجهة رغم إنها تُقرأ من قاموس وقت التشغيل.
DEGREE_LABELS = {
    1: (_l("علاقة درجة أولى"), 0.5),
    2: (_l("علاقة درجة ثانية"), 0.25),
}


def _parent_ids(animal_id: int) -> set[int]:
    a = Animal.query.get(animal_id)
    if not a:
        return set()
    return {p for p in (a.mother_id, a.father_id) if p}


def _ancestors_by_generation(animal_id: int, max_gen: int = 2) -> dict[int, int]:
    """يرجّع {معرّف السلف: أقرب جيل وصل له} حتى `max_gen` أجيال للخلف."""
    result: dict[int, int] = {}
    frontier = [(animal_id, 0)]
    seen = {animal_id}
    while frontier:
        current_id, gen = frontier.pop()
        if gen >= max_gen:
            continue
        for parent_id in _parent_ids(current_id):
            if parent_id not in seen:
                seen.add(parent_id)
                result[parent_id] = gen + 1
                frontier.append((parent_id, gen + 1))
            elif parent_id not in result or result[parent_id] > gen + 1:
                result[parent_id] = gen + 1
    return result


def check_relationship(female_id: int, male_id: int) -> dict | None:
    """يرجّع {degree, label, coefficient_percent, relation_type} لو فيه
    علاقة قرابة درجة أولى/ثانية موثّقة بالأنساب المسجَّلة، وإلا None."""
    if not female_id or not male_id or female_id == male_id:
        return None

    female = Animal.query.get(female_id)
    male = Animal.query.get(male_id)
    if not female or not male:
        return None

    # درجة أولى: أحدهما أب/أم للثاني
    if female.mother_id == male.id or female.father_id == male.id:
        return {"degree": 1, "relation_type": _l("أب/ابنة أو أم/ابنة")}
    if male.mother_id == female.id or male.father_id == female.id:
        return {"degree": 1, "relation_type": _l("أم/ابن أو أب/ابن")}

    # درجة أولى/ثانية: إخوة (يشتركون بأحد الأبوين أو كليهما)
    female_parents = {female.mother_id, female.father_id} - {None}
    male_parents = {male.mother_id, male.father_id} - {None}
    shared_parents = female_parents & male_parents
    if len(shared_parents) == 2:
        return {"degree": 1, "relation_type": _l("إخوة أشقاء كاملين (نفس الأب والأم)")}
    if len(shared_parents) == 1:
        return {"degree": 2, "relation_type": _l("إخوة من طرف واحد (نفس الأب أو نفس الأم)")}

    # درجة ثانية: جد/حفيدة بأي اتجاه
    female_ancestors = _ancestors_by_generation(female.id, max_gen=2)
    male_ancestors = _ancestors_by_generation(male.id, max_gen=2)
    if female_ancestors.get(male.id) == 2:
        return {"degree": 2, "relation_type": _l("جد/حفيدة")}
    if male_ancestors.get(female.id) == 2:
        return {"degree": 2, "relation_type": _l("جدة/حفيد")}

    # درجة ثانية: عم/خال أو عمة/خالة (سلف مشترك بجيل مختلف: أحدهما
    # جيل 1 (أب/أم مباشر) والثاني جيل 2 (جد/جدة) لنفس السلف).
    common = set(female_ancestors) & set(male_ancestors)
    for ancestor_id in common:
        gens = {female_ancestors[ancestor_id], male_ancestors[ancestor_id]}
        if gens == {1, 2}:
            return {"degree": 2, "relation_type": _l("عم/عمة أو خال/خالة")}

    return None


def relationship_warning(female_id: int, male_id: int) -> dict | None:
    result = check_relationship(female_id, male_id)
    if not result:
        return None
    label, coefficient = DEGREE_LABELS[result["degree"]]
    result["label"] = label
    result["coefficient_percent"] = round(coefficient * 100)
    return result
