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
from datetime import date
from app.models import (
    Animal, VetVisit, Disease, Vaccination, Finance,
    Mating, Pregnancy, SonarResult, TwinEstrusProgram,
    AnimalWeight, AnimalNote, MilkRecord, FeedBarnPlan,
)


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


def _feed_cost_estimate(animal: Animal) -> dict:
    """
    تقدير تقريبي لنصيب الحيوان من تكلفة العلف (بند إضافي، 2026-07-23) —
    **تقدير مو رقم دقيق**، موضّح صراحة بالواجهة: يفترض إن الحيوان قضى
    كامل مدته بالمزرعة بنفس حظيرته وخطة تغذيتها الحالية، لأن النظام ما
    عنده جدول يتتبّع تاريخ انتقال الحيوان بين الحظائر (نفس القيد الموثّق
    ببند 18 لتقرير تكلفة الرأس الشهرية). لو الحيوان تنقّل حظائر فعلياً،
    الرقم يبتعد عن الواقع بقدر التنقّل.
    """
    today = date.today()
    since = animal.entry_date or animal.birth_date or (animal.created_at.date() if animal.created_at else today)
    days = max((today - since).days, 0)
    if not animal.barn_id:
        return {"daily_cost": 0, "days": days, "total": 0, "available": False}

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
    vet_visits = VetVisit.query.filter_by(animal_id=animal.id).order_by(VetVisit.date.desc()).all()
    diseases = Disease.query.filter_by(animal_id=animal.id).order_by(Disease.date.desc()).all()
    vaccinations = Vaccination.query.filter_by(animal_id=animal.id).order_by(Vaccination.date.desc()).all()
    weights = AnimalWeight.query.filter_by(animal_id=animal.id).order_by(AnimalWeight.date.desc()).all()
    notes = AnimalNote.query.filter_by(animal_id=animal.id).order_by(AnimalNote.date.desc()).all()
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
        Mating.query.filter((Mating.female_id == animal.id) | (Mating.male_id == animal.id))
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

    # نصيب الرأس من المصاريف غير المباشرة (بند إضافي، 2026-07-23) —
    # إيجار/صيانة/رواتب **صارت متتبَّعة الآن** عبر `Finance.is_indirect`،
    # وتُوزَّع بالتساوي على عدد الرؤوس النشطة الحالي (نفس منهجية تقرير
    # "تكلفة الرأس الشهرية" ببند 18، بقرارك الصريح). النطاق الزمني: من
    # تاريخ دخول هذا الرأس للمزرعة (ولادة/شراء/دخول) لحد اليوم — قبل
    # دخوله ما كان جزء من القطيع، فما يتحمّل مصاريفه.
    since = animal.entry_date or animal.birth_date or animal.purchase_date or (animal.created_at.date() if animal.created_at else date.today())
    active_head_count = Animal.query.filter_by(status="active").count()
    indirect_total_since_entry = sum(
        f.amount for f in Finance.query.filter(
            Finance.operation_type == "expense", Finance.is_indirect.is_(True),
            Finance.is_cancelled.is_(False), Finance.date >= since,
        ).all()
    )
    indirect_cost_share = round(indirect_total_since_entry / active_head_count, 2) if active_head_count else 0

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
