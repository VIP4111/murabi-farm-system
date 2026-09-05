"""
خدمة "صفحة تفاصيل الرأس الشاملة" (البند 9 بالمواصفة الرئيسية).

الفكرة: بدل ما مستخدم النظام يفتّش سجل حيوان معيّن بجداول منفصلة (زيارات،
أمراض، تطعيمات، تكاثر...)، هذه الدالة تجمع كل شي مرتبط بحيوان واحد بمكان
واحد، وتبني منها "تسلسل زمني موحّد" مرتب بالتاريخ.

قرار تصميم: التسلسل الزمني يُبنى من الجداول الفعلية مباشرة (VetVisit,
Disease...) مو من CycleEvent — CycleEvent مخصص لمحاسبة بوابات محرك دورة
الإنتاج (انظر app/core/cycle_engine.py) وتفاصيله تقنية (اسم مرحلة/حالة
بوابة)، بينما التسلسل هنا لازم يكون مقروء بمحتوى فعلي (اسم مرض، اسم لقاح...).
صفحة "دورة الإنتاج" الحالية (animal_workflow.html) تبقى المصدر لأحداث
البوابات، وهذه الصفحة تكمّلها بمحتوى السجلات نفسها.
"""
from datetime import date, timedelta
from sqlalchemy.orm import joinedload
from app.extensions import db
from app.models import (
    Animal, VetVisit, Disease, Vaccination, Finance,
    Mating, Pregnancy, SonarResult, TwinEstrusProgram,
    AnimalWeight, AnimalNote, MilkRecord, FeedBarnPlan,
)

# تقدير القيمة السوقية من مبيعات حقيقية مشابهة (بند إضافي 254)
COMPARABLE_SALES_WINDOW_DAYS = 90
COMPARABLE_AGE_TOLERANCE_DAYS = 60
COMPARABLE_SALES_MIN_SAMPLE = 2


def _age_label(birth_date) -> str | None:
    if not birth_date:
        return None
    days = (date.today() - birth_date).days
    if days < 0:
        return None
    if days < 60:
        return f"{days} يوم"
    if days < 730:
        return f"{days // 30} شهر"
    return f"{days // 365} سنة"


def _current_feed_plans_by_barn() -> dict:
    """كل خطط التغذية الفعّالة اليوم، مجموعة حسب الحظيرة (آخر خطة لكل
    حظيرة لو فيه أكثر من وحدة). بند إصلاح أداء لاحق (`break_even_summary`
    كان يستدعي `_feed_cost_estimate` لكل رأس نشط، وكل استدعاء يسوي
    استعلام FeedBarnPlan منفصل له وحده — نفس مشكلة N+1) — نجيبها *مرة
    وحدة* لكل الحظائر بدل استعلام لكل رأس على حدة."""
    today = date.today()
    plans = (
        FeedBarnPlan.query
        .filter(FeedBarnPlan.start_date <= today)
        .filter((FeedBarnPlan.end_date.is_(None)) | (FeedBarnPlan.end_date >= today))
        .order_by(FeedBarnPlan.start_date.asc())
        .all()
    )
    # الترتيب تصاعدي وكل حظيرة تُكتب فوق سابقتها — النتيجة النهائية
    # لكل حظيرة هي الخطة ذات أحدث start_date، نفس `.order_by(desc()).first()`.
    by_barn = {}
    for p in plans:
        by_barn[p.barn_id] = p
    return by_barn


def _feed_cost_estimate(animal: Animal, plan_by_barn: dict | None = None) -> dict:
    """
    تقدير تقريبي لنصيب الحيوان من تكلفة العلف (بند إضافي، 2026-07-23) —
    **تقدير مو رقم دقيق**، موضّح صراحة بالواجهة: يفترض إن الحيوان قضى
    كامل مدته بالمزرعة بنفس حظيرته وخطة تغذيتها الحالية، لأن النظام ما
    عنده جدول يتتبّع تاريخ انتقال الحيوان بين الحظائر (نفس القيد الموثّق
    ببند 18 لتقرير تكلفة الرأس الشهرية). لو الحيوان تنقّل حظائر فعلياً،
    الرقم يبتعد عن الواقع بقدر التنقّل.

    `plan_by_barn` اختياري (بند إصلاح أداء لاحق) — لو مُمرَّر (من
    `break_even_summary` اللي يستدعي هذي الدالة لكل رأس نشط بالمزرعة)،
    نستخدمه بدل استعلام FeedBarnPlan منفصل لكل رأس؛ فاضي = السلوك
    الأصلي (استعلام مباشر)، يبقى صحيحاً لاستخدام رأس واحد (`get_profile`).
    """
    today = date.today()
    since = animal.entry_date or animal.birth_date or (animal.created_at.date() if animal.created_at else today)
    days = max((today - since).days, 0)
    if not animal.barn_id:
        return {"daily_cost": 0, "days": days, "total": 0, "available": False}

    if plan_by_barn is not None:
        plan = plan_by_barn.get(animal.barn_id)
    else:
        plan = (
            FeedBarnPlan.query.filter_by(barn_id=animal.barn_id)
            .filter(FeedBarnPlan.start_date <= today)
            .filter((FeedBarnPlan.end_date.is_(None)) | (FeedBarnPlan.end_date >= today))
            .order_by(FeedBarnPlan.start_date.desc())
            .first()
        )
    if not plan:
        return {"daily_cost": 0, "days": days, "total": 0, "available": False}

    from app.feed.feed_service import ration_profile
    profile = ration_profile(plan.ration)
    daily_cost = round(profile["cost_per_kg"] * plan.daily_qty_per_animal_kg, 2)
    return {"daily_cost": daily_cost, "days": days, "total": round(daily_cost * days, 2), "available": True}


def get_profile(animal: Animal) -> dict:
    # إصلاح أداء — بلاغ مستخدم: "بطيء وهو يعرض بيانات الحيوان". السبب:
    # التسلسل الزمني تحت يوصل لعلاقات (`v.doctor`, `n.created_by`,
    # `m.male`/`m.female`) داخل حلقة `for` — بدون تحميل مسبق (eager
    # load)، كل وصول كذا يسوي استعلام قاعدة بيانات منفصل لكل صف على حدة
    # (N+1 كلاسيكي) — لرأس عنده تاريخ طويل (زيارات/ملاحظات/تقريع كثير)
    # هذا يعني عشرات الاستعلامات الإضافية بكل فتحة صفحة، فوق قاعدة
    # بيانات بعيدة (Neon) كل استعلام له زمن شبكة حقيقي. `joinedload`
    # يجيب العلاقة بنفس الاستعلام الأصلي (JOIN وحدة) بدل استعلام منفصل
    # لكل صف — نفس النتيجة بالضبط، أسرع بكثير.
    vet_visits = (
        VetVisit.query.options(joinedload(VetVisit.doctor))
        .filter_by(animal_id=animal.id).order_by(VetVisit.date.desc()).all()
    )
    diseases = Disease.query.filter_by(animal_id=animal.id).order_by(Disease.date.desc()).all()
    vaccinations = Vaccination.query.filter_by(animal_id=animal.id).order_by(Vaccination.date.desc()).all()
    weights = AnimalWeight.query.filter_by(animal_id=animal.id).order_by(AnimalWeight.date.desc()).all()
    notes = (
        AnimalNote.query.options(joinedload(AnimalNote.created_by))
        .filter_by(animal_id=animal.id).order_by(AnimalNote.date.desc()).all()
    )
    milk_records = (
        MilkRecord.query.filter_by(animal_id=animal.id)
        .order_by(MilkRecord.date.desc(), MilkRecord.session.desc()).all()
    )
    births = Animal.query.filter_by(mother_id=animal.id).order_by(Animal.birth_date.desc()).all()
    finance_rows = (
        Finance.query.filter_by(related_animal_id=animal.id, is_cancelled=False)
        .order_by(Finance.date.desc()).all()
    )

    matings = (
        Mating.query.options(joinedload(Mating.male), joinedload(Mating.female))
        .filter((Mating.female_id == animal.id) | (Mating.male_id == animal.id))
        .order_by(Mating.date.desc()).all()
    )
    pregnancies = Pregnancy.query.filter_by(female_id=animal.id).order_by(Pregnancy.date.desc()).all()
    sonar_results = SonarResult.query.filter_by(ewe_id=animal.id).order_by(SonarResult.exam_date.desc()).all()
    twin_programs = (
        TwinEstrusProgram.query
        .filter((TwinEstrusProgram.ewe_id == animal.id) | (TwinEstrusProgram.ram_id == animal.id))
        .order_by(TwinEstrusProgram.start_date.desc()).all()
    )

    open_diseases_count = sum(1 for d in diseases if d.status == "active")

    timeline = []
    for v in vet_visits:
        timeline.append({
            "date": v.date, "category": "سجل بيطري", "icon": "🩺",
            "label": v.diagnosis or "زيارة بيطرية",
            "detail": f"الطبيب: {v.doctor.name if v.doctor else '-'}",
        })
    for d in diseases:
        timeline.append({
            "date": d.date, "category": "مرض", "icon": "🌡️",
            "label": d.disease_name,
            "detail": "مفتوح" if d.status == "active" else f"مغلق — {d.recovery_note or ''}".strip(" —"),
        })
    for vc in vaccinations:
        timeline.append({
            "date": vc.date, "category": "تحصين", "icon": "💉",
            "label": vc.vaccine_name,
            "detail": f"الجرعة القادمة: {vc.next_due_date}" if vc.next_due_date else "",
        })
    for w in weights:
        timeline.append({
            "date": w.date, "category": "وزن", "icon": "⚖️",
            "label": f"{w.weight} كجم",
            "detail": w.notes or "",
        })
    for mr in milk_records:
        timeline.append({
            "date": mr.date, "category": "حليب", "icon": "🥛",
            "label": f"{mr.quantity_liters} لتر ({mr.session})",
            "detail": mr.notes or "",
        })
    for n in notes:
        timeline.append({
            "date": n.date, "category": "ملاحظة", "icon": "📝",
            "label": n.note[:80] + ("…" if len(n.note) > 80 else ""),
            "detail": n.created_by.name if n.created_by else "",
        })
    for b in births:
        if b.birth_date:
            timeline.append({
                "date": b.birth_date, "category": "ولادة", "icon": "🍼",
                "label": f"ولادة {b.animal_no} ({b.gender or '-'})",
                "detail": f"الوزن عند الولادة: {b.weight} كجم" if b.weight else "",
            })
    for f in finance_rows:
        op_labels = {"sale": "بيع", "purchase": "شراء", "expense": "مصروف"}
        timeline.append({
            "date": f.date, "category": "مالية", "icon": "💰",
            "label": f"{op_labels.get(f.operation_type, f.operation_type)} — {f.amount} ",
            "detail": f.item or f.description or "",
        })
    for m in matings:
        role = "أنثى" if m.female_id == animal.id else "فحل"
        other = m.male if m.female_id == animal.id else m.female
        timeline.append({
            "date": m.date, "category": "تقريع", "icon": "🐑",
            "label": f"تقريع — {role}",
            "detail": f"الطرف الآخر: {other.animal_no if other else (m.male_note or '-')}",
        })
    for p in pregnancies:
        timeline.append({
            "date": p.date, "category": "تشخيص حمل", "icon": "🤰",
            "label": "حمل مؤكد" if p.confirmed else "فحص حمل",
            "detail": f"عدد الأجنة: {p.embryo_count}" if p.embryo_count else "",
        })
    for s in sonar_results:
        timeline.append({
            "date": s.exam_date, "category": "فحص سونار", "icon": "📡",
            "label": s.result or "فحص سونار",
            "detail": f"عدد الأجنة: {s.embryo_count}" if s.embryo_count else "",
        })

    timeline.sort(key=lambda e: e["date"] or animal.created_at.date(), reverse=True)

    # تقرير تكلفة الرأس الفردي (بند إضافي، 2026-07-23) — يجمع كل مصادر
    # التكلفة المتاحة فعلياً بالنظام لهذا الحيوان تحديداً.
    direct_medical_cost = round(
        sum(v.cost or 0 for v in vet_visits)
        + sum(d.treatment_cost or 0 for d in diseases)
        + sum(vc.cost or 0 for vc in vaccinations), 2,
    )
    purchase_cost = round(sum(f.amount for f in finance_rows if f.operation_type == "purchase"), 2)
    feed_cost_estimate = _feed_cost_estimate(animal)

    # نصيب الرأس من المصاريف غير المباشرة (بند إضافي، 2026-07-23،
    # مصحَّحة ببند 253) — إيجار/صيانة/رواتب متتبَّعة عبر
    # `Finance.is_indirect`، وتُوزَّع على **متوسط** عدد الرؤوس خلال
    # فترة وجود هذا الرأس بالقطيع (مو عدد اليوم الثابت — كان يشوّه
    # الرقم لو تغيّر حجم القطيع بين دخول الرأس واليوم؛ نفس المبدأ
    # المصحَّح بتقرير "تكلفة الرأس الشهرية" ببند 251، بس بمتوسط بدل
    # تفصيل شهري كامل — أخف حسابياً لصفحة تُفتح لكل رأس بشكل متكرر).
    # النطاق الزمني: من تاريخ دخول هذا الرأس للمزرعة (ولادة/شراء/دخول)
    # لحد اليوم — قبل دخوله ما كان جزء من القطيع، فما يتحمّل مصاريفه.
    since = animal.entry_date or animal.birth_date or animal.purchase_date or (animal.created_at.date() if animal.created_at else date.today())
    from app.core.finance_report_service import average_head_count_between
    avg_head_count = average_head_count_between(since, date.today())
    indirect_total_since_entry = sum(
        f.amount for f in Finance.query.filter(
            Finance.operation_type == "expense", Finance.is_indirect.is_(True),
            Finance.is_cancelled.is_(False), Finance.date >= since,
        ).all()
    )
    indirect_cost_share = round(indirect_total_since_entry / avg_head_count, 2) if avg_head_count else 0

    total_cost_estimate = round(
        purchase_cost + direct_medical_cost + feed_cost_estimate["total"] + indirect_cost_share, 2
    )

    return {
        "animal": animal,
        "age_label": _age_label(animal.birth_date),
        "vet_visits": vet_visits,
        "diseases": diseases,
        "vaccinations": vaccinations,
        "weights": weights,
        "milk_records": milk_records,
        "notes": notes,
        "births": births,
        "finance_rows": finance_rows,
        "matings": matings,
        "pregnancies": pregnancies,
        "sonar_results": sonar_results,
        "twin_programs": twin_programs,
        "open_diseases_count": open_diseases_count,
        "timeline": timeline,
        "direct_medical_cost": direct_medical_cost,
        "purchase_cost": purchase_cost,
        "feed_cost_estimate": feed_cost_estimate,
        "indirect_cost_share": indirect_cost_share,
        "total_cost_estimate": total_cost_estimate,
    }


def _all_comparable_sales_in_window() -> list:
    """كل عمليات البيع (مع الرأس المرتبط) خلال آخر
    `COMPARABLE_SALES_WINDOW_DAYS` يوم، بدون فلترة نوع/جنس — بند إصلاح
    أداء لاحق: `break_even_summary` كان يستدعي
    `estimate_market_value_from_comparable_sales` لكل رأس نشط، وكل
    استدعاء يسوي استعلام JOIN منفصل له وحده (N+1). نجيب المبيعات *مرة
    وحدة* هنا، وتفلترها كل استدعاء لاحقاً بالذاكرة (بند نوع/جنس/عمر) —
    نفس النتيجة بالضبط، استعلام واحد بدل واحد لكل رأس."""
    cutoff = date.today() - timedelta(days=COMPARABLE_SALES_WINDOW_DAYS)
    return (
        db.session.query(Finance, Animal)
        .join(Animal, Finance.related_animal_id == Animal.id)
        .filter(
            Finance.operation_type == "sale", Finance.is_cancelled.is_(False),
            Finance.date >= cutoff,
        ).all()
    )


def estimate_market_value_from_comparable_sales(animal: Animal, all_sales: list | None = None) -> dict | None:
    """يقدّر القيمة السوقية لرأس نشط من عمليات بيع حقيقية سابقة لرؤوس
    مشابهة (بند إضافي 254، طلبك الصريح: "ليش الهامش ما يعتمد على أرقام
    البيع الذي يتم عن طريق المزرعة") — بدل قيمة يدوية تصدأ (كانت
    القيمة الوحيدة المتاحة سابقاً، `ProductionWorkflow.estimated_value`)،
    يحسب حي من مبيعات حقيقية (نفس النوع + الجنس، وعمر قريب لو متوفر
    تاريخ ميلاد الطرفين) ضمن آخر `COMPARABLE_SALES_WINDOW_DAYS` يوم —
    يتحدّث تلقائياً كل مرة تُفتح الشاشة، ما يصدأ أبداً. يرجع `None`
    صراحةً لو ما فيه عينة كافية (ما نخترع رقم من عدم).

    `all_sales` اختياري (بند إصلاح أداء لاحق) — لو مُمرَّر (من
    `break_even_summary`، مُجهَّز مسبقاً بـ`_all_comparable_sales_in_window`)،
    نفلتره بالذاكرة بدل استعلام JOIN منفصل؛ فاضي = السلوك الأصلي
    (استعلام مباشر)، يبقى صحيحاً لاستخدام رأس واحد."""
    all_sales = all_sales if all_sales is not None else _all_comparable_sales_in_window()
    sales = [
        (fin, other) for fin, other in all_sales
        if other.id != animal.id and other.species == animal.species and other.gender == animal.gender
    ]
    if not sales:
        return None

    target_age_days = (date.today() - animal.birth_date).days if animal.birth_date else None
    narrow = []
    for fin, other in sales:
        if target_age_days is not None and other.birth_date:
            age_at_sale = (fin.date - other.birth_date).days
            if abs(age_at_sale - target_age_days) <= COMPARABLE_AGE_TOLERANCE_DAYS:
                narrow.append(fin.amount)

    prices = narrow if len(narrow) >= COMPARABLE_SALES_MIN_SAMPLE else [fin.amount for fin, _ in sales]
    if len(prices) < COMPARABLE_SALES_MIN_SAMPLE:
        return None

    return {"value": round(sum(prices) / len(prices), 2), "sample_count": len(prices),
            "narrowed_by_age": narrow is prices}


def break_even_summary() -> list[dict]:
    """محرك التحليل المالي ونقطة التعادل (بند إضافي 176، محدَّثة ببند
    254) — لكل رأس نشط: التكلفة الإجمالية المقدَّرة منذ الدخول (= سعر
    البيع الأدنى لتحقيق التعادل، نفس رقم `total_cost_estimate` بتقرير
    الرأس الفردي) مقابل قيمة تقديرية للبيع. أولوية مصدر القيمة
    التقديرية: (1) تقدير محسوب حي من مبيعات حقيقية مشابهة
    (`estimate_market_value_from_comparable_sales` — يتحدّث تلقائياً
    كل مرة، ما يصدأ)، (2) وإلا القيمة اليدوية المسجَّلة
    (`ProductionWorkflow.estimated_value` من شاشة "بيانات تخطيط
    السوق")، (3) وإلا ما فيه قيمة أصلاً — الهامش ما يُحسب (ما نخترع
    سعر سوق غير موجود)."""
    animals = Animal.query.filter_by(status="active").all()
    from app.core.finance_report_service import average_head_count_between, build_entry_exit_maps
    entry_exit_maps = build_entry_exit_maps()
    since_cache: dict = {}
    avg_head_count_cache: dict = {}

    # إصلاح أداء — بلاغ مستخدم: "ضعف في التصفح غير سريع" (استكمال نفس
    # جولة التدقيق اللي كشفت مشكلة صفحة تفاصيل الحيوان). كانت هذي
    # الحلقة تسوي ٦+ استعلامات منفصلة *لكل رأس نشط على حدة* (Finance
    # مرتين، VetVisit، Disease، Vaccination، خطة علف، ومبيعات مشابهة) —
    # لمزرعة عندها 50 رأس هذا يعني 300+ استعلام لفتحة صفحة وحدة. نجيب
    # كل شي مرة وحدة قبل الحلقة، ونجمّعه حسب animal_id بالذاكرة — نفس
    # النتيجة بالضبط، عدد استعلامات ثابت بغض النظر عن عدد الرؤوس.
    from collections import defaultdict
    animal_ids = [a.id for a in animals]
    finance_by_animal = defaultdict(list)
    for f in Finance.query.filter(Finance.related_animal_id.in_(animal_ids), Finance.is_cancelled.is_(False)).all():
        finance_by_animal[f.related_animal_id].append(f)
    vet_visits_by_animal = defaultdict(list)
    for v in VetVisit.query.filter(VetVisit.animal_id.in_(animal_ids)).all():
        vet_visits_by_animal[v.animal_id].append(v)
    diseases_by_animal = defaultdict(list)
    for d in Disease.query.filter(Disease.animal_id.in_(animal_ids)).all():
        diseases_by_animal[d.animal_id].append(d)
    vaccinations_by_animal = defaultdict(list)
    for vc in Vaccination.query.filter(Vaccination.animal_id.in_(animal_ids)).all():
        vaccinations_by_animal[vc.animal_id].append(vc)
    plan_by_barn = _current_feed_plans_by_barn()
    all_comparable_sales = _all_comparable_sales_in_window()
    from app.models.cycle import ProductionWorkflow
    workflow_by_animal = {
        w.animal_id: w for w in ProductionWorkflow.query.filter(ProductionWorkflow.animal_id.in_(animal_ids)).all()
    }

    rows = []
    for animal in animals:
        finance_rows = finance_by_animal.get(animal.id, [])
        purchase_cost = round(sum(f.amount for f in finance_rows if f.operation_type == "purchase"), 2)
        vet_visits = vet_visits_by_animal.get(animal.id, [])
        diseases = diseases_by_animal.get(animal.id, [])
        vaccinations = vaccinations_by_animal.get(animal.id, [])
        direct_medical_cost = round(
            sum(v.cost or 0 for v in vet_visits) + sum(d.treatment_cost or 0 for d in diseases)
            + sum(vc.cost or 0 for vc in vaccinations), 2,
        )
        feed_cost_estimate = _feed_cost_estimate(animal, plan_by_barn=plan_by_barn)

        since = animal.entry_date or animal.birth_date or animal.purchase_date or (
            animal.created_at.date() if animal.created_at else date.today())
        if since not in since_cache:
            since_cache[since] = sum(
                f.amount for f in Finance.query.filter(
                    Finance.operation_type == "expense", Finance.is_indirect.is_(True),
                    Finance.is_cancelled.is_(False), Finance.date >= since,
                ).all()
            )
        if since not in avg_head_count_cache:
            avg_head_count_cache[since] = average_head_count_between(since, date.today(), maps=entry_exit_maps)
        avg_head_count = avg_head_count_cache[since]
        indirect_cost_share = round(since_cache[since] / avg_head_count, 2) if avg_head_count else 0

        break_even_price = round(
            purchase_cost + direct_medical_cost + feed_cost_estimate["total"] + indirect_cost_share, 2
        )
        # القيمة التقديرية (بند إضافي 254) — الأولوية لتقدير محسوب من
        # مبيعات حقيقية مشابهة (يتحدّث تلقائياً، ما يصدأ)، وإلا رجوع
        # للقيمة اليدوية (بند 176، شاشة "بيانات تخطيط السوق") لو
        # مسجَّلة، وإلا ما فيه قيمة أصلاً (الهامش ما يُحسب).
        auto_estimate = estimate_market_value_from_comparable_sales(animal, all_sales=all_comparable_sales)
        wf = workflow_by_animal.get(animal.id)
        manual_value = wf.estimated_value if wf and wf.estimated_value else None
        if auto_estimate:
            estimated_value = auto_estimate["value"]
            estimate_source = "auto"
            estimate_sample_count = auto_estimate["sample_count"]
        elif manual_value is not None:
            estimated_value = manual_value
            estimate_source = "manual"
            estimate_sample_count = None
        else:
            estimated_value = None
            estimate_source = None
            estimate_sample_count = None
        margin = round(estimated_value - break_even_price, 2) if estimated_value is not None else None
        rows.append({
            "animal": animal,
            "break_even_price": break_even_price,
            "estimated_value": estimated_value,
            "estimate_source": estimate_source,
            "estimate_sample_count": estimate_sample_count,
            "margin": margin,
            "at_risk": margin is not None and margin < 0,
        })

    # الرؤوس المهدَّدة بخسارة (هامش سالب) أول القائمة، ثم اللي ما فيها
    # قيمة تقديرية أصلاً (يحتاج المالك يعبّيها)، ثم الباقي مرتّبة تنازلياً
    # حسب أعلى تكلفة تعادل (الأعلى تكلفة تستاهل مراجعة أقرب).
    rows.sort(key=lambda r: (
        0 if r["at_risk"] else (1 if r["estimated_value"] is None else 2),
        -r["break_even_price"],
    ))
    return rows
