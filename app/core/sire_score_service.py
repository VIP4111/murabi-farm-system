"""تقييم أداء الفحول (بند إضافي 183) — إحصائيات حقيقية مبنية حصراً على
سجلات موجودة أصلاً بالنظام (Mating، Pregnancy، Animal.father_id)، صفر
تقدير أو اختراع بيانات.

**قرار تصميم مقصود**: ما نبني "درجة" واحدة (Score) توزن كل المؤشرات
بمعادلة سرية وتوهم بحسم — نعرض كل مؤشر بمفرده بشفافية، وصاحب الحلال
يقرر التوازن بينها بنفسه (فحل بمعدل توائم عالي بس صحة مواليد أضعف
قرار مختلف عن فحل متوسط بكل شي). هذا يتفادى تحيّز رقم واحد مضلّل."""
from app.models import Animal, Mating, Pregnancy


def sire_scorecard(male: Animal) -> dict:
    matings = Mating.query.filter_by(male_id=male.id).all()
    matings_count = len(matings)

    pregnancies = (
        Pregnancy.query.join(Mating, Pregnancy.mating_id == Mating.id)
        .filter(Mating.male_id == male.id)
        .all()
    )
    confirmed = [p for p in pregnancies if p.confirmed]
    conception_rate = round(len(confirmed) / matings_count * 100, 1) if matings_count else None

    twin_eligible = [p for p in confirmed if p.embryo_count]
    twin_pregnancies = [p for p in twin_eligible if p.embryo_count >= 2]
    twin_rate = round(len(twin_pregnancies) / len(twin_eligible) * 100, 1) if twin_eligible else None

    offspring = Animal.query.filter_by(father_id=male.id).all()
    offspring_count = len(offspring)
    offspring_alive = [a for a in offspring if a.status != "dead"]
    survival_rate = round(len(offspring_alive) / offspring_count * 100, 1) if offspring_count else None

    birth_weights = [a.weight for a in offspring if a.weight]
    avg_birth_weight = round(sum(birth_weights) / len(birth_weights), 2) if birth_weights else None

    return {
        "sire": male,
        "matings_count": matings_count,
        "conception_rate": conception_rate,
        "twin_rate": twin_rate,
        "twin_sample_size": len(twin_eligible),
        "offspring_count": offspring_count,
        "survival_rate": survival_rate,
        "avg_birth_weight": avg_birth_weight,
    }


def all_sire_scorecards() -> list[dict]:
    """كل فحل عنده تقريع مسجَّل واحد على الأقل — مرتّبة تنازلياً حسب
    عدد المواليد الفعليين (أقوى دليل نتيجة حقيقية، مو تقديري)."""
    sire_ids = {m.male_id for m in Mating.query.filter(Mating.male_id.isnot(None)).all()}
    sires = Animal.query.filter(Animal.id.in_(sire_ids)).all() if sire_ids else []
    cards = [sire_scorecard(s) for s in sires]
    cards.sort(key=lambda c: c["offspring_count"], reverse=True)
    return cards
