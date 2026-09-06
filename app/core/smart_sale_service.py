"""
محرك البيع الذكي وتفادي الخسارة (بند 19 بالمواصفة الرئيسية).

القواعد هنا بالضبط كما وصفتها (2026-07-23) — مو تخمين مننا:

**الذكور**: العمر هو الأهم. البيع العادي بعمر 6 أشهر (180 يوم). بيع
الأضاحي يحتاج عمر "فوق" 6 أشهر — السن الشرعي الأدنى للجذعة من الضأن هو
6 أشهر كاملة بالضبط (حديث "لا تذبحوا إلا مسنة إلا أن يعسر عليكم فتذبحوا
جذعة من الضأن")، فحطينا هامش أمان قليل فوقه (195 يوم افتراضي، قابل
للتعديل من الإعدادات). الوزن ثانوي: لو متوقف/يتراجع، يستهلك علف بدون
عائد يستاهل الانتظار.

**الإناث**: نظام "علامات" مباشر مو درجة موزونة — أي علامة من الأربع
تعني بيع فوري بغض النظر عن باقي العوامل:
1. تأخر حملها أكثر من شهرين (بدون تقريع/حمل جديد، وبعد ما خلصت فترة
   الراحة الطبيعية بعد الولادة لو عندها).
2. ما حملت إطلاقاً رغم بلوغها سن التقريع من فترة طويلة.
3. ترفض إرضاع مولودها (علامة يدوية — Animal.refuses_nursing).
4. الدرة (الضرع) تالفة (علامة يدوية — Animal.udder_damaged).

**الدرجة**: 0-100، كل ما زادت زاد إلحاح البيع. الهامش المستهدف والأعمار
كلها من FarmSettings — قابلة للتعديل من شاشة الإعدادات بدون كود.
"""
from datetime import date, timedelta
from flask_babel import gettext as _
from app.models import Animal, AnimalWeight, VetVisit, Disease, Mating, FarmSettings


def _age_days(animal: Animal):
    ref = animal.birth_date or animal.purchase_date or animal.entry_date
    if not ref:
        return None
    return (date.today() - ref).days


def _weight_trend(animal: Animal, last_two_weights: list | None = None) -> str | None:
    """يرجّع 'up'/'flat'/'down' من آخر قيدين وزن، أو None لو ما فيه كفاية بيانات.

    `last_two_weights` اختياري (بند إصلاح أداء) — لو مُمرَّر (من
    `get_recommendations` المجمَّعة)، نستخدمه بدل استعلام AnimalWeight
    منفصل؛ فاضي = السلوك الأصلي (استعلام مباشر)."""
    records = last_two_weights if last_two_weights is not None else (
        AnimalWeight.query.filter_by(animal_id=animal.id)
        .order_by(AnimalWeight.date.desc()).limit(2).all()
    )
    if len(records) < 2:
        return None
    latest, previous = records[0], records[1]
    if latest.weight > previous.weight:
        return "up"
    if latest.weight < previous.weight:
        return "down"
    return "flat"


def _current_cost(animal: Animal, health_cost_map: dict | None = None) -> float:
    """`health_cost_map` اختياري (بند إصلاح أداء) — دفتر {animal_id:
    مجموع تكاليف VetVisit+Disease} مُجهَّز مسبقاً (من `get_recommendations`)
    بدل استعلامين منفصلين لكل رأس؛ فاضي = السلوك الأصلي."""
    cost = animal.price or 0
    if health_cost_map is not None:
        cost += health_cost_map.get(animal.id, 0)
    else:
        cost += sum(v.cost or 0 for v in VetVisit.query.filter_by(animal_id=animal.id).all())
        cost += sum(d.treatment_cost or 0 for d in Disease.query.filter_by(animal_id=animal.id).all())
    return cost


def _bulk_health_cost_map(animal_ids: list) -> dict:
    """بند إصلاح أداء (بحث "سرعة التنقل") — `_current_cost` كانت تسوي
    استعلامين منفصلين (VetVisit + Disease) *لكل رأس على حدة*، وتُستدعى
    مرتين لكل رأس (من `_profit_margin_percent` و`marginal_feeding_signal`
    كل وحدة لحالها) بشاشة "البيع الذكي" — أثقل شاشة بالنظام من ناحية
    الاستعلامات. الإصلاح: استعلامان ثابتان إجمالاً (GROUP BY animal_id)
    لكل الرؤوس دفعة وحدة."""
    from app.extensions import db
    if not animal_ids:
        return {}
    cost_map: dict[int, float] = {}
    for row in (
        db.session.query(VetVisit.animal_id, db.func.sum(VetVisit.cost))
        .filter(VetVisit.animal_id.in_(animal_ids)).group_by(VetVisit.animal_id).all()
    ):
        cost_map[row[0]] = cost_map.get(row[0], 0) + (row[1] or 0)
    for row in (
        db.session.query(Disease.animal_id, db.func.sum(Disease.treatment_cost))
        .filter(Disease.animal_id.in_(animal_ids)).group_by(Disease.animal_id).all()
    ):
        cost_map[row[0]] = cost_map.get(row[0], 0) + (row[1] or 0)
    return cost_map


def _bulk_last_two_weights(animal_ids: list) -> dict:
    """بند إصلاح أداء — نفس فلسفة `_bulk_health_cost_map`، لآخر قيدين
    وزن لكل رأس. استعلام واحد يجيب كل أوزان الرؤوس المطلوبة (مرتبة)،
    ثم تقسيم بالذاكرة — بدل استعلام منفصل لكل رأس."""
    if not animal_ids:
        return {}
    rows = (
        AnimalWeight.query.filter(AnimalWeight.animal_id.in_(animal_ids))
        .order_by(AnimalWeight.animal_id, AnimalWeight.date.desc()).all()
    )
    by_animal: dict[int, list] = {}
    for w in rows:
        bucket = by_animal.setdefault(w.animal_id, [])
        if len(bucket) < 2:
            bucket.append(w)
    return by_animal


def marginal_feeding_signal(animal: Animal, *, last_two_weights: list | None = None,
                             plan_by_barn: dict | None = None, health_cost_map: dict | None = None) -> dict | None:
    """الحاسبة التنبؤية للبيع — مؤشر داخلي بس (بند إضافي، 2026-07-24،
    بقرارك الصريح: مؤشر تكلفة/نمو داخلي، مو تنبؤ بسعر سوق خارجي — النظام
    ما عنده أي بيانات أسعار سوق أصلاً). يقارن **التكلفة الحدية الحالية**
    (تكلفة علف يومية ÷ معدل زيادة الوزن الأخير) بـ**متوسط تكلفة الكيلو
    التاريخي** لنفس الرأس (كل التكاليف المتراكمة ÷ الوزن الحالي). لو
    التكلفة الحدية أعلى بوضوح، معناه الاستمرار بتسمينه صار أغلى نسبياً
    من متوسط تكلفته لحد الآن — إشارة اقتصادية داخلية بس، مو توقيتاً
    مالياً فعلياً (يحتاج بيانات سوق ما تتوفر بالنظام).

    المعاملات الثلاثة الأخيرة اختيارية (بند إصلاح أداء، بحث "سرعة
    التنقل") — لو مُمرَّرة (من `get_recommendations` المجمَّعة)، تُستخدم
    بدل استعلامات منفصلة لكل رأس؛ فاضية = السلوك الأصلي."""
    from app.core.animal_profile_service import _feed_cost_estimate

    records = last_two_weights if last_two_weights is not None else (
        AnimalWeight.query.filter_by(animal_id=animal.id)
        .order_by(AnimalWeight.date.desc()).limit(2).all()
    )
    if len(records) < 2 or not animal.weight:
        return None
    latest, previous = records[0], records[1]
    days_between = (latest.date - previous.date).days
    gain = latest.weight - previous.weight
    if days_between <= 0 or gain <= 0:
        return None
    gain_per_day = gain / days_between

    feed_est = _feed_cost_estimate(animal, plan_by_barn=plan_by_barn)
    if not feed_est["available"] or not feed_est["daily_cost"]:
        return None
    marginal_cost_per_kg = feed_est["daily_cost"] / gain_per_day

    total_cost = _current_cost(animal, health_cost_map=health_cost_map) + feed_est["total"]
    if total_cost <= 0:
        return None
    historical_cost_per_kg = total_cost / animal.weight

    if marginal_cost_per_kg <= historical_cost_per_kg * 1.2:
        return None  # لسا ضمن المعتاد، ما فيه إشارة تستاهل التنبيه

    return {
        "marginal_cost_per_kg": round(marginal_cost_per_kg, 2),
        "historical_cost_per_kg": round(historical_cost_per_kg, 2),
        "reason": _(
            "التكلفة الحدية الحالية للكيلو (%(marginal)s) صارت أعلى بوضوح من متوسط تكلفة الكيلو التاريخي (%(historical)s) — استمرار التسمين قد ما يستاهل التكلفة (مؤشر داخلي، راجعه قبل القرار).",
            marginal=round(marginal_cost_per_kg, 2), historical=round(historical_cost_per_kg, 2),
        ),
    }


def _profit_margin_percent(animal: Animal, health_cost_map: dict | None = None) -> float | None:
    wf = animal.workflow
    if not wf or not wf.estimated_value:
        return None
    cost = _current_cost(animal, health_cost_map=health_cost_map)
    if cost <= 0:
        return None
    return (wf.estimated_value - cost) / cost * 100


def _window_for_score(score: int) -> str:
    if score >= 80:
        return _("خلال 7 أيام")
    if score >= 60:
        return _("خلال 14 يوم")
    if score >= 40:
        return _("خلال 30 يوم")
    if score >= 20:
        return _("خلال 60 يوم")
    return _("احتفاظ حالياً")


def _label_for_score(score: int) -> str:
    if score >= 80:
        return _("بيع الآن")
    if score >= 60:
        return _("بيع قريب")
    if score >= 40:
        return _("مراقبة")
    return _("احتفاظ")


def _evaluate_male(animal: Animal, fs: FarmSettings, ctx: dict | None = None) -> tuple[int, list[str]]:
    ctx = ctx or {}
    # ملاحظة: `.get(animal.id, [])` مو `None` — لو الدفتر المجمَّع
    # موجود بـ`ctx`، غياب مفتاح الرأس فيه يعني "ما عنده أوزان مسجَّلة"
    # فعلياً (قائمة فاضية)، مو "ما فيه دفتر أصلاً" (اللي يرجّع None
    # ويشغّل استعلام مباشر بديل بالدوال الفرعية).
    weights = ctx["weights_by_animal"].get(animal.id, []) if "weights_by_animal" in ctx else None
    health_cost_map = ctx.get("health_cost_map")
    plan_by_barn = ctx.get("plan_by_barn")

    reasons = []
    score = 0
    age = _age_days(animal)
    if age is not None:
        if age >= fs.udhiyah_min_age_days:
            score += 50
            reasons.append(_("تجاوز سن جاهزية الأضاحي (%(min)s يوم) — عمره %(age)s يوم", min=fs.udhiyah_min_age_days, age=age))
        elif age >= fs.regular_sale_age_days:
            score += 40
            reasons.append(_("تجاوز سن البيع العادي (%(min)s يوم) — عمره %(age)s يوم", min=fs.regular_sale_age_days, age=age))
        else:
            score += round(30 * age / fs.regular_sale_age_days)
            reasons.append(_("لسا ما وصل سن البيع العادي (عمره %(age)s من %(min)s يوم)", age=age, min=fs.regular_sale_age_days))

    trend = _weight_trend(animal, last_two_weights=weights)
    if trend in ("flat", "down"):
        score += 30
        reasons.append(_("الوزن متوقف أو يتراجع — يستهلك علف بدون عائد يستاهل الانتظار"))
    elif trend == "up":
        reasons.append(_("الوزن يتحسن — يستاهل الانتظار شوي قبل البيع"))

    margin = _profit_margin_percent(animal, health_cost_map=health_cost_map)
    if margin is not None and margin >= fs.target_profit_margin_percent:
        score += 25
        reasons.append(_("هامش الربح الحالي %(margin)s%% ≥ الهدف %(target)s%% — وقت جيد للبيع", margin=f"{margin:.0f}", target=f"{fs.target_profit_margin_percent:.0f}"))

    signal = marginal_feeding_signal(animal, last_two_weights=weights, plan_by_barn=plan_by_barn, health_cost_map=health_cost_map)
    if signal:
        score += 20
        reasons.append(signal["reason"])

    return min(score, 100), reasons


def _is_reproductively_delayed(animal: Animal, fs: FarmSettings) -> bool:
    from app.core.cycle_engine import _is_confirmed_pregnant

    if _is_confirmed_pregnant(animal):
        return False

    last_child = (
        Animal.query.filter_by(mother_id=animal.id)
        .order_by(Animal.birth_date.desc()).first()
    )
    if last_child and last_child.birth_date:
        rest_end = last_child.birth_date + timedelta(days=fs.min_rest_after_birth_days)
        if date.today() < rest_end:
            return False  # لسا بفترة الراحة الطبيعية بعد الولادة

    last_mating = (
        Mating.query.filter_by(female_id=animal.id)
        .order_by(Mating.date.desc()).first()
    )
    if last_mating:
        return (date.today() - last_mating.date).days > fs.female_delayed_conception_days

    age = _age_days(animal)
    from app.core.animal_filters_service import BREEDING_ADULT_MIN_AGE_DAYS
    if age is not None and age >= BREEDING_ADULT_MIN_AGE_DAYS + fs.female_delayed_conception_days:
        return True
    return False


def bulk_is_reproductively_delayed(females: list, fs: FarmSettings) -> dict:
    """نسخة مجمَّعة من `_is_reproductively_delayed()` — بحث "مشاكل
    تشغيلية" (2026-09-06) لقى إن هذي الدالة تسوي حتى 4 استعلامات منفصلة
    *لكل أنثى على حدة* (حمل مؤكَّد + سونار + آخر مولود + آخر تلقيح)،
    وتُستدعى بحلقة for على كل الإناث النشطات بتنبيه "تأخر شياع" —
    الأثقل بكل التنبيهات (61 استعلام لـ15 رأس بالقياس الفعلي). نفس
    المنطق بالضبط، بس بـ4 استعلامات ثابتة إجمالاً (وحدة لكل مصدر بيانات،
    مجمَّعة بـIN/GROUP BY) بدل استعلام لكل رأس."""
    from app.extensions import db
    from app.models import Pregnancy, SonarResult
    from app.core.animal_filters_service import BREEDING_ADULT_MIN_AGE_DAYS

    ids = [a.id for a in females]
    if not ids:
        return {}

    pregnant_ids = {
        row[0] for row in
        Pregnancy.query.filter(Pregnancy.female_id.in_(ids), Pregnancy.confirmed.is_(True))
        .with_entities(Pregnancy.female_id).all()
    }
    pregnant_ids |= {
        row[0] for row in
        SonarResult.query.filter(SonarResult.ewe_id.in_(ids), SonarResult.result == "حامل")
        .with_entities(SonarResult.ewe_id).all()
    }

    last_child_by_mother = dict(
        db.session.query(Animal.mother_id, db.func.max(Animal.birth_date))
        .filter(Animal.mother_id.in_(ids), Animal.birth_date.isnot(None))
        .group_by(Animal.mother_id).all()
    )
    last_mating_by_female = dict(
        db.session.query(Mating.female_id, db.func.max(Mating.date))
        .filter(Mating.female_id.in_(ids))
        .group_by(Mating.female_id).all()
    )

    today = date.today()
    result = {}
    for a in females:
        if a.id in pregnant_ids:
            result[a.id] = False
            continue
        last_child_date = last_child_by_mother.get(a.id)
        if last_child_date:
            rest_end = last_child_date + timedelta(days=fs.min_rest_after_birth_days)
            if today < rest_end:
                result[a.id] = False
                continue
        last_mating_date = last_mating_by_female.get(a.id)
        if last_mating_date:
            result[a.id] = (today - last_mating_date).days > fs.female_delayed_conception_days
            continue
        age = _age_days(a)
        result[a.id] = bool(
            age is not None and age >= BREEDING_ADULT_MIN_AGE_DAYS + fs.female_delayed_conception_days
        )
    return result


def _evaluate_female(animal: Animal, fs: FarmSettings, ctx: dict | None = None) -> tuple[int, list[str]]:
    ctx = ctx or {}
    weights = ctx["weights_by_animal"].get(animal.id, []) if "weights_by_animal" in ctx else None
    health_cost_map = ctx.get("health_cost_map")
    is_delayed = ctx["delayed_map"].get(animal.id, False) if "delayed_map" in ctx else _is_reproductively_delayed(animal, fs)

    flags = []
    if animal.refuses_nursing:
        flags.append(_("ترفض إرضاع مولودها"))
    if animal.udder_damaged:
        flags.append(_("الضرع/الدرة تالفة"))
    if is_delayed:
        flags.append(_("تأخر حملها أكثر من %(n)s يوم بدون تقريع/حمل جديد", n=fs.female_delayed_conception_days))

    if flags:
        score = min(90 + (len(flags) - 1) * 3, 100)
        return score, flags

    # ما فيه علامة بيع — تقييم أخف يعتمد على العمر/الوزن/الهامش، بميل
    # افتراضي نحو الاحتفاظ (أنثى منتجة بدون مشاكل لازم تبقى بالقطيع).
    reasons = []
    score = 0
    trend = _weight_trend(animal, last_two_weights=weights)
    if trend == "down":
        score += 15
        reasons.append(_("الوزن يتراجع — يحتاج متابعة"))
    margin = _profit_margin_percent(animal, health_cost_map=health_cost_map)
    if margin is not None and margin >= fs.target_profit_margin_percent:
        score += 15
        reasons.append(_("هامش الربح الحالي %(margin)s%% ≥ الهدف %(target)s%%", margin=f"{margin:.0f}", target=f"{fs.target_profit_margin_percent:.0f}"))
    if not reasons:
        reasons.append(_("بدون علامات بيع — أنثى منتجة، يُفضّل الاحتفاظ"))
    return score, reasons


def evaluate_animal(animal: Animal, fs: FarmSettings | None = None, ctx: dict | None = None) -> dict:
    fs = fs or FarmSettings.get()
    if animal.gender == "ذكر":
        score, reasons = _evaluate_male(animal, fs, ctx=ctx)
    else:
        score, reasons = _evaluate_female(animal, fs, ctx=ctx)
    return {
        "animal": animal,
        "score": score,
        "label": _label_for_score(score),
        "window": _window_for_score(score),
        "reasons": reasons,
    }


def get_recommendations() -> list[dict]:
    """بند إصلاح أداء حرج (بحث "سرعة التنقل") — كل رأس نشط كان يسوي
    حتى 10 استعلامات منفصلة له لحاله (وزن مرتين، تكلفة صحية مرتين،
    تأخر شياع حتى 4، خطة علف مرة) بهذي الشاشة — أثقل شاشة بالنظام،
    وتُستدعى كمان تلقائياً بكل تحميل للرئيسية عبر `alerts_service.
    _ready_to_sell_now`. الإصلاح: كل البيانات المساعدة تُجهَّز *مرة
    وحدة* لكل الرؤوس دفعة وحدة (`ctx`) بدل استعلام لكل رأس."""
    from app.core.animal_profile_service import _current_feed_plans_by_barn
    from sqlalchemy.orm import joinedload

    fs = FarmSettings.get()
    animals = Animal.query.filter_by(status="active").options(joinedload(Animal.workflow)).all()
    animal_ids = [a.id for a in animals]
    females = [a for a in animals if a.gender != "ذكر"]

    ctx = {
        "weights_by_animal": _bulk_last_two_weights(animal_ids),
        "health_cost_map": _bulk_health_cost_map(animal_ids),
        "plan_by_barn": _current_feed_plans_by_barn(),
        "delayed_map": bulk_is_reproductively_delayed(females, fs),
    }

    rows = [evaluate_animal(a, fs=fs, ctx=ctx) for a in animals]
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows
