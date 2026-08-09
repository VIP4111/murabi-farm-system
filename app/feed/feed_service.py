"""
حاسبة العلائق — تقدير احتياج يومي لكل رأس، ومقارنة الوصفات الجاهزة لاقتراح
الأرخص من المخزون الفعلي.

**تنبيه مهم**: الأرقام بدالة `PHYSIOLOGICAL_TARGETS` تقديرات مبسّطة عامة
للمجترات الصغيرة (غنم/ماعز)، مو توصية بيطرية معتمدة لمزرعتك. عدّلها حسب
توصية طبيبك أو مرجع تغذية معتمد قبل ما تعتمد عليها فعلياً بقرارات شراء.
"""
from datetime import date, timedelta
from app.extensions import db
from app.models import Feed, FeedRation, FeedMovement, FeedBarnPlan


BASE_DMI_PERCENT_OF_BODYWEIGHT = 0.025  # 2.5% من وزن الجسم كنقطة بداية

PHYSIOLOGICAL_TARGETS = {
    # state: (multiplier على الكمية, %بروتين خام مستهدف, طاقة ممثلة مستهدفة كيلوكالوري/كجم)
    "maintenance": (1.00, 10.0, 2200),
    "growth": (1.15, 14.0, 2600),
    "late_pregnancy": (1.30, 13.0, 2500),
    "lactation": (1.60, 16.0, 2800),
}

PURPOSE_TO_STATE = {
    "نمو": "growth",
    "تسمين": "growth",
    "نفاس": "lactation",
    "حمل_متأخر": "late_pregnancy",
    "صيانة": "maintenance",
}


def infer_physiological_state(animal) -> str:
    """تخمين الحالة الفسيولوجية من دورة الإنتاج الحالية للحيوان — تقدير
    آلي، يقدر المستخدم يتجاوزه يدوياً بشاشة الحاسبة."""
    wf = animal.workflow
    if not wf:
        return "maintenance"
    if wf.route == "female_breeding" and wf.current_stage == 6:
        return "late_pregnancy"
    if wf.route == "female_breeding" and wf.current_stage in (7, 8):
        return "lactation"
    if wf.route in ("fattening", "newborn") and wf.current_stage in (8, 9):
        return "growth"
    return "maintenance"


def daily_requirement(*, weight_kg: float, state: str) -> dict:
    multiplier, protein_target, energy_target = PHYSIOLOGICAL_TARGETS.get(state, PHYSIOLOGICAL_TARGETS["maintenance"])
    dmi_kg = round(weight_kg * BASE_DMI_PERCENT_OF_BODYWEIGHT * multiplier, 3)
    return {
        "state": state,
        "daily_dry_matter_kg": dmi_kg,
        "target_protein_percent": protein_target,
        "target_energy_kcal_per_kg": energy_target,
    }


def ration_profile(ration: FeedRation) -> dict:
    """يحسب القيمة الغذائية الموزونة وتكلفة الكيلو لوصفة معيّنة من مكوّناتها الفعلية."""
    total_percent = sum(item.percent for item in ration.items) or 1
    protein = sum((item.percent / total_percent) * (item.feed.protein_percent or 0) for item in ration.items)
    energy = sum((item.percent / total_percent) * (item.feed.energy_kcal_per_kg or 0) for item in ration.items)
    cost_per_kg = sum((item.percent / total_percent) * (item.feed.unit_price or 0) for item in ration.items)
    # كالسيوم/فسفور (بند إضافي 51) — أساس حارس نسبة 2:1
    calcium = sum((item.percent / total_percent) * (item.feed.calcium_percent or 0) for item in ration.items)
    phosphorus = sum((item.percent / total_percent) * (item.feed.phosphorus_percent or 0) for item in ration.items)
    return {
        "protein_percent": round(protein, 2), "energy_kcal_per_kg": round(energy, 1), "cost_per_kg": round(cost_per_kg, 3),
        "calcium_percent": round(calcium, 3), "phosphorus_percent": round(phosphorus, 3),
    }


def concentrate_percent(ration: FeedRation) -> float:
    """% وزن الوصفة اللي مصدرها مكوّنات مصنَّفة "مركّز" (`Feed.feed_class`)
    — أساس حارس منع الزيادة المفاجئة (بند إضافي 51)."""
    total = sum(item.percent for item in ration.items) or 1
    concentrate = sum(item.percent for item in ration.items if item.feed.feed_class == "concentrate")
    return round(concentrate / total * 100, 1)


def ca_phosphorus_warning(profile: dict, fs) -> dict | None:
    """تحذير نسبة الكالسيوم:الفسفور (بند إضافي 51) — الهدف 2:1 (قابل
    للتعديل)، بهامش تسامح. تحذير + تجاوز بسبب صريح، مو حظراً (قرارك)."""
    ca, p = profile.get("calcium_percent"), profile.get("phosphorus_percent")
    if not ca or not p:
        return None
    ratio = round(ca / p, 2)
    if abs(ratio - fs.ca_phosphorus_target_ratio) <= fs.ca_phosphorus_tolerance:
        return None
    return {
        "ratio": ratio, "target": fs.ca_phosphorus_target_ratio,
        "message": (
            f"نسبة الكالسيوم:الفسفور بهذي الوصفة {ratio}:1 — بعيدة عن الهدف الآمن "
            f"({fs.ca_phosphorus_target_ratio}:1 ± {fs.ca_phosphorus_tolerance}) — خطر حصوات المثانة "
            "خصوصاً للذكور. راجع التركيبة أو أدخل سبب تجاوز صريح."
        ),
    }


def concentrate_increase_warning(*, barn_id: int, new_ration: FeedRation, new_start_date, fs) -> dict | None:
    """حظر الزيادة المفاجئة للمركزات (بند إضافي 51) — يقارن نسبة
    المركزات بالوصفة الجديدة مقابل الوصفة اللي كانت فعّالة بالحظيرة
    قبل `concentrate_increase_window_days` يوماً (افتراضي 7) — تحذير +
    تجاوز بسبب صريح (قرارك)، مو حظراً نهائياً."""
    from datetime import timedelta
    if not new_ration.items:
        return None
    new_pct = concentrate_percent(new_ration)
    lookback_date = new_start_date - timedelta(days=fs.concentrate_increase_window_days)
    prior_plan = (
        FeedBarnPlan.query.filter(FeedBarnPlan.barn_id == barn_id, FeedBarnPlan.start_date <= lookback_date)
        .order_by(FeedBarnPlan.start_date.desc()).first()
    )
    if not prior_plan or not prior_plan.ration.items:
        return None
    prior_pct = concentrate_percent(prior_plan.ration)
    increase = round(new_pct - prior_pct, 1)
    if increase <= fs.concentrate_increase_max_percent_weekly:
        return None
    return {
        "prior_percent": prior_pct, "new_percent": new_pct, "increase": increase,
        "message": (
            f"نسبة المركزات ترتفع من {prior_pct}% إلى {new_pct}% (زيادة {increase} نقطة) خلال "
            f"{fs.concentrate_increase_window_days} أيام — أعلى من الحد الآمن "
            f"({fs.concentrate_increase_max_percent_weekly}% أسبوعياً)، خطر لكم/تخمّر. "
            "قسّمها على مراحل تدريجية أو أدخل سبب تجاوز صريح."
        ),
    }


def recommend_rations(*, requirement: dict, limit: int = 5) -> list[dict]:
    """يرتّب الوصفات الموجودة حسب أقرب تطابق للاحتياج وأرخص تكلفة، مع علامة
    توفّر المخزون الحالي."""
    results = []
    for ration in FeedRation.query.all():
        if not ration.items:
            continue
        profile = ration_profile(ration)
        daily_cost = round(profile["cost_per_kg"] * requirement["daily_dry_matter_kg"], 2)
        protein_gap = abs(profile["protein_percent"] - requirement["target_protein_percent"])
        energy_gap = abs(profile["energy_kcal_per_kg"] - requirement["target_energy_kcal_per_kg"])
        match_score = max(0, 100 - protein_gap * 4 - energy_gap / 20)

        stock_ok = True
        for item in ration.items:
            needed_for_item = requirement["daily_dry_matter_kg"] * (item.percent / 100)
            if (item.feed.available_qty or 0) < needed_for_item:
                stock_ok = False
                break

        results.append({
            "ration": ration,
            "profile": profile,
            "daily_cost_per_animal": daily_cost,
            "match_score": round(match_score),
            "stock_ok": stock_ok,
        })

    results.sort(key=lambda r: (-r["match_score"], r["daily_cost_per_animal"]))
    return results[:limit]


def record_movement(*, feed: Feed, movement_type: str, quantity: float, barn_id=None,
                     animal_id=None, note=None, created_by_id=None) -> FeedMovement:
    # ربط إجباري بالحظيرة عند الاستهلاك (بند إضافي، 2026-07-23) — حركة
    # "صادر" بدون حظيرة تفقد تتبّعها بالكامل ويستحيل حساب تكلفة يومية
    # صحيحة لأي حظيرة منها (بند 18 وتقرير تكلفة الرأس الفردي بند 45
    # كلاهما يعتمدان على ربط الاستهلاك بحظيرة). الوارد (شراء) ما يحتاج
    # حظيرة أصلاً — يدخل المخزون العام قبل التوزيع.
    if movement_type == "out" and not barn_id:
        raise ValueError('حركة الصادر (الاستهلاك) لازم تُربَط بحظيرة — بدونها ما تنحسب التكلفة اليومية صح.')

    before = feed.available_qty or 0
    if movement_type == "in":
        feed.add_stock(quantity)
    else:
        feed.deduct_stock(quantity)
        from app.core.stock_alert_service import check_feed_stock
        check_feed_stock(feed)
    after = feed.available_qty or 0

    mv = FeedMovement(
        feed_id=feed.id, movement_type=movement_type, quantity=quantity,
        before_qty=before, after_qty=after, barn_id=barn_id, animal_id=animal_id,
        note=note, created_by_id=created_by_id,
    )
    db.session.add(mv)
    db.session.add(feed)
    db.session.commit()
    return mv


def barn_daily_blend(*, barn_id: int) -> dict:
    """خلطة علف يومية **مجمَّعة لكل الحظيرة** (بند إضافي 134) — الفرق
    عن `optimizer()` الموجودة أصلاً: تلك تحسب لرأس واحد يختاره المستخدم
    يدوياً، هذي تجمع احتياج كل الرؤوس النشطة بالحظيرة (كل رأس بوزنه
    وحالته الفسيولوجية المستنتجة تلقائياً عبر `infer_physiological_state`)
    بطلب واحد لـ`optimize_blend` — نفس فلسفة "النظام يقرر" اللي طلبتها،
    بدون ما تحتاج تفتح الحاسبة لكل رأس لحاله. النعام مستثنى (أهدافه
    الغذائية مختلفة تماماً عن المجترات، نفس استثناء فلتر "المرضعات")."""
    from app.models import Animal

    animals = Animal.query.filter_by(barn_id=barn_id, status="active").filter(Animal.species != "ostrich").all()
    with_weight = [a for a in animals if a.weight]
    skipped_no_weight = len(animals) - len(with_weight)

    if not with_weight:
        return {
            "feasible": False,
            "reason": "ما فيه رؤوس نشطة بهذي الحظيرة عندها وزن مسجَّل — سجّل وزن الرؤوس أولاً.",
            "animals_included": 0, "animals_skipped": skipped_no_weight,
        }

    requirements = [
        daily_requirement(weight_kg=a.weight, state=infer_physiological_state(a))
        for a in with_weight
    ]
    total_dmi = sum(r["daily_dry_matter_kg"] for r in requirements)
    target_protein = sum(r["target_protein_percent"] * r["daily_dry_matter_kg"] for r in requirements) / total_dmi
    target_energy = sum(r["target_energy_kcal_per_kg"] * r["daily_dry_matter_kg"] for r in requirements) / total_dmi

    aggregate_requirement = {
        "state": "barn_aggregate",
        "daily_dry_matter_kg": round(total_dmi, 3),
        "target_protein_percent": round(target_protein, 2),
        "target_energy_kcal_per_kg": round(target_energy, 1),
    }
    usable_feeds = Feed.query.filter_by(status="active").all()
    result = optimize_blend(requirement=aggregate_requirement, feeds=usable_feeds)
    result["animals_included"] = len(with_weight)
    result["animals_skipped"] = skipped_no_weight
    return result


def optimize_blend(*, requirement: dict, feeds: list, max_fraction: float = 0.6) -> dict:
    """موازِن العليقة التلقائي (بند إضافي، 2026-07-24) — يحل "مسألة
    الحمية" (Diet Problem) الكلاسيكية ببرمجة خطية حقيقية
    (`scipy.optimize.linprog`)، مو ترتيب وصفات جاهزة (تلك موجودة أصلاً
    بـ`recommend_rations`). يبني خلطة **من الصفر** من كل مكوّنات العلف
    الخام النشطة، بأقل تكلفة تحقق أهداف البروتين والطاقة المطلوبة.

    `max_fraction` = أقصى نسبة يسمح بيها لأي مكوّن واحد من إجمالي الخلطة
    (افتراضياً 60%) — قيد واقعي بسيط يمنع الحل من اقتراح مكوّن واحد
    بنسبة 100% حتى لو كان الأرخص، لأن خلطة حقيقية عملياً تحتاج تنويعاً.
    **تنبيه صادق**: القيد مبسّط اجتهادي، مو معادلة تغذية معتمدة — راجع
    طبيب/مختص تغذية قبل اعتماد أي خلطة فعلياً بمزرعتك."""
    usable_feeds = [f for f in feeds if f.unit_price is not None and f.protein_percent is not None and f.energy_kcal_per_kg is not None]
    if not usable_feeds:
        return {"feasible": False, "reason": "ما فيه مكوّنات علف عندها بروتين وطاقة وسعر وحدة مسجَّلة بالكامل — أكمل بيانات مكوّنات العلف أولاً."}

    import numpy as np
    from scipy.optimize import linprog

    dmi = requirement["daily_dry_matter_kg"]
    target_protein = requirement["target_protein_percent"]
    target_energy = requirement["target_energy_kcal_per_kg"]
    n = len(usable_feeds)

    c = [f.unit_price for f in usable_feeds]
    A_eq = [[1.0] * n]
    b_eq = [dmi]
    A_ub = [
        [-(f.protein_percent / 100.0) for f in usable_feeds],
        [-(f.energy_kcal_per_kg) for f in usable_feeds],
    ]
    b_ub = [-(target_protein / 100.0) * dmi, -target_energy * dmi]
    # سقف واقعي لكل مكوّن، لكن **بدون ما يخلي المسألة مستحيلة رياضياً** —
    # لو عدد المكوّنات المتاحة قليل، سقف صارم (60%) يمنع قيد "المجموع =
    # الاحتياج اليومي" من التحقق أصلاً (مثال: مكوّن وحيد بسقف 60% ما
    # يقدر يوصل لـ100% من الاحتياج، فيصير الحل "غير ممكن" بالغلط رغم إن
    # المكوّن كافٍ غذائياً). نرفع السقف الفعّال لأي مكوّن لأعلى قيمة بين
    # النسبة المطلوبة وحصته المتساوية من عدد المكوّنات (1/n) لضمان إن
    # مجموع السقوف يغطي 100% دائماً.
    effective_fraction = max(max_fraction, 1.0 / n)
    bounds = [(0, effective_fraction * dmi) for _ in usable_feeds]

    res = linprog(c=c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")

    if not res.success:
        return {
            "feasible": False,
            "reason": "ما فيه خلطة ممكنة بمكوّنات العلف الحالية تحقق الاحتياج المطلوب — أضف مكوّنات أعلى بروتين/طاقة، أو راجع الأهداف.",
        }

    blend = []
    total_cost = 0.0
    for feed, qty in zip(usable_feeds, res.x):
        if qty < 0.001:
            continue
        cost = round(qty * feed.unit_price, 3)
        total_cost += cost
        blend.append({
            "feed": feed, "quantity_kg": round(qty, 3),
            "percent": round(100 * qty / dmi, 1) if dmi else 0,
            "cost": cost,
            "stock_ok": (feed.available_qty or 0) >= qty,
        })
    blend.sort(key=lambda b: -b["percent"])

    return {
        "feasible": True,
        "daily_dry_matter_kg": dmi,
        "blend": blend,
        "total_daily_cost": round(total_cost, 2),
        "all_stock_ok": all(b["stock_ok"] for b in blend),
    }


def calculate_fcr(*, barn_id: int, start_date: date, end_date: date) -> dict:
    """معدل التحويل الغذائي FCR لحظيرة خلال فترة (بند إضافي، 2026-07-24)
    — FCR = كجم علف مستهلك ÷ كجم زيادة وزن، لكل رؤوس الحظيرة النشطة
    الحالية مجتمعة (رقم أقل = كفاءة تحويل أعلى).

    **تنبيهات صادقة**: (1) دقته تعتمد على انتظام تسجيل الوزن بجدول
    "الأوزان" لكل حيوان — رأس بدون وزنين مسجَّلين بالفترة يُستبعد من
    حساب الزيادة (يظهر بـ`animals_with_data` مقابل `animals_total`).
    (2) التكلفة تُحسب بسعر الوحدة *الحالي* للعلف — النظام ما يتتبّع
    تاريخ تغيّر الأسعار بعد (نفس القيد الموثّق بتقرير تكلفة الرأس
    الشهرية، بند 18). (3) الرؤوس المحسوبة هي المسجَّلة بالحظيرة *الآن*،
    مو بالضرورة كل رأس كان فيها طوال الفترة بالكامل."""
    from datetime import datetime, time
    from app.models import Animal
    from app.models.animal_log import AnimalWeight

    range_start = datetime.combine(start_date, time.min)
    range_end = datetime.combine(end_date, time.max)
    movements = (FeedMovement.query
                 .filter_by(barn_id=barn_id, movement_type="out")
                 .filter(FeedMovement.created_at >= range_start, FeedMovement.created_at <= range_end)
                 .all())
    total_feed_kg = sum(m.quantity for m in movements)
    total_feed_cost = sum(m.quantity * (m.feed.unit_price or 0) for m in movements)

    animals = Animal.query.filter_by(barn_id=barn_id, status="active").all()
    total_gain = 0.0
    animals_with_data = 0
    for animal in animals:
        start_w = (AnimalWeight.query.filter(AnimalWeight.animal_id == animal.id, AnimalWeight.date <= start_date)
                   .order_by(AnimalWeight.date.desc()).first())
        end_w = (AnimalWeight.query.filter(AnimalWeight.animal_id == animal.id, AnimalWeight.date <= end_date)
                 .order_by(AnimalWeight.date.desc()).first())
        if start_w and end_w and end_w.id != start_w.id and end_w.weight > start_w.weight:
            total_gain += (end_w.weight - start_w.weight)
            animals_with_data += 1

    return {
        "total_feed_kg": round(total_feed_kg, 2),
        "total_feed_cost": round(total_feed_cost, 2),
        "total_weight_gain_kg": round(total_gain, 2),
        "fcr": round(total_feed_kg / total_gain, 2) if total_gain else None,
        "cost_per_kg_gained": round(total_feed_cost / total_gain, 2) if total_gain else None,
        "animals_with_data": animals_with_data,
        "animals_total": len(animals),
    }


HEAT_RECENT_WINDOW_DAYS = 3
HEAT_BASELINE_WINDOW_DAYS = 14
HEAT_DROP_THRESHOLD_PERCENT = 15.0


def heat_fcr_signal(*, barn_id: int, as_of_date: date | None = None) -> dict | None:
    """يربط انخفاض استهلاك العلف بموجة حر بمؤشر THI (بند إضافي 49) —
    يقارن كجم علف/رأس/يوم بآخر أيام حر بمتوسط فترة أساس أهدأ قبلها.
    **توصية فقط يراجعها المالك** (بقرارك الصريح) — ما يشغّل موازِن
    العليقة تلقائياً ولا يعدّل أي وصفة، فقط يقترح مراجعتها.

    **تنبيه صادق**: يفترض عدد رؤوس الحظيرة النشط *الحالي* ثابت طوال
    الفترتين (نفس قيد `calculate_fcr` أعلاه) — تغيّر عدد الرؤوس بمنتصف
    الفترة (بيع/شراء) يشوّه المقارنة."""
    from datetime import datetime, time
    from app.models import Animal, WeatherReading

    as_of = as_of_date or date.today()
    recent_start = as_of - timedelta(days=HEAT_RECENT_WINDOW_DAYS - 1)
    baseline_end = recent_start - timedelta(days=1)
    baseline_start = baseline_end - timedelta(days=HEAT_BASELINE_WINDOW_DAYS - 1)

    animals_count = Animal.query.filter_by(barn_id=barn_id, status="active").count()
    if not animals_count:
        return None

    hot_days = (
        WeatherReading.query.filter(
            WeatherReading.date >= recent_start,
            WeatherReading.date <= as_of,
            WeatherReading.stress_level.in_(("moderate", "severe", "emergency")),
        ).all()
    )
    if not hot_days:
        return None

    def _avg_daily_per_animal(start, end):
        range_start = datetime.combine(start, time.min)
        range_end = datetime.combine(end, time.max)
        total = (
            db.session.query(db.func.coalesce(db.func.sum(FeedMovement.quantity), 0))
            .filter(
                FeedMovement.barn_id == barn_id,
                FeedMovement.movement_type == "out",
                FeedMovement.created_at >= range_start,
                FeedMovement.created_at <= range_end,
            )
            .scalar()
        )
        days = (end - start).days + 1
        return (total or 0) / days / animals_count

    recent_avg = _avg_daily_per_animal(recent_start, as_of)
    baseline_avg = _avg_daily_per_animal(baseline_start, baseline_end)
    if baseline_avg <= 0 or recent_avg <= 0:
        return None

    drop_pct = round((1 - recent_avg / baseline_avg) * 100, 1)
    if drop_pct < HEAT_DROP_THRESHOLD_PERCENT:
        return None

    worst = max(hot_days, key=lambda r: r.thi)
    return {
        "recent_avg_kg_per_head": round(recent_avg, 3),
        "baseline_avg_kg_per_head": round(baseline_avg, 3),
        "drop_pct": drop_pct,
        "peak_thi": worst.thi,
        "recommendation": (
            f"استهلاك العلف انخفض {drop_pct}% بالحظيرة أثناء إجهاد حراري "
            f"(THI={worst.thi}) مقارنة بمعدلها المعتاد — فكّر بزيادة تركيز "
            f"المركزات بالعليقة (طاقة/بروتين بحجم أصغر) بدل زيادة الكمية "
            f"اللي الحيوان أصلاً مقلّل أكلها. راجع موازِن العليقة لإعادة "
            f"احتساب خلطة مناسبة — القرار والتنفيذ يرجعان للمالك."
        ),
    }


def days_until_stockout(feed: Feed, lookback_days: int = 14) -> float | None:
    """متوسط الاستهلاك اليومي بآخر N يوم، مقسوم على المتوفر حالياً."""
    since = date.today() - timedelta(days=lookback_days)
    consumed = (db.session.query(db.func.coalesce(db.func.sum(FeedMovement.quantity), 0))
                .filter(FeedMovement.feed_id == feed.id, FeedMovement.movement_type == "out",
                        FeedMovement.created_at >= since)
                .scalar())
    if not consumed:
        return None
    avg_daily = consumed / lookback_days
    if avg_daily <= 0:
        return None
    return round((feed.available_qty or 0) / avg_daily, 1)
