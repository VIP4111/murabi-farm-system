"""
منطق العمل الصحي: تسجيل زيارة/مرض/تطعيم، مع تطبيق قاعدة "فترة السحب"
تلقائياً من بيانات الدواء بالصيدلية (بدل ما تُحسب يدوياً أو تُنسى).
"""
from datetime import date, timedelta
from app.extensions import db
from app.models import Pharmacy, VetVisit, Disease, Vaccination, AuditLog, Symptom, DiseaseSymptomLink, DiseaseType


class IncompleteRecordError(Exception):
    """سلامة البيانات (بند إضافي، 2026-07-23) — يُرفع لما سجل طبي يحاول
    يُحفظ ناقصاً بشكل يكسر تتبّع العلاج أو حساب التكلفة (دواء محدد بدون
    جرعة، مثلاً)."""


# دليل الحقن الميداني (بند إضافي، 2026-07-24) — مرجع عام موثّق بأساسيات
# رعاية المجترات الصغيرة (غنم/ماعز)، بمستوى "إرشاد ميداني عام" مو
# "بروتوكول طبي دقيق لحالة معيّنة". **مقصود إنه عام وغير مرتبط بدواء
# محدد** — تفاصيل أي دواء بعينه (جرعة، مكان محدد لو مختلف) تبقى
# مسؤولية `standard_dosage_note` اللي يكتبه الدكتور بنفسه. راجع الدكتور
# المعالج دائماً لتفاصيل خاصة بحالة الحيوان.
INJECTION_GUIDE = {
    "حقن عضل": {
        "title": "حقن عضل (IM)",
        "notes": "بعضلات الرقبة الجانبية أو الفخذ الخلفي عند البالغين، بعيداً عن العمود الفقري والأعصاب الكبيرة. دوّر مكان الحقن بين الجانبين لتفادي تندّب متكرر بنفس المكان. إبرة أقصر وأدق للحملان الصغيرة.",
    },
    "حقن وريدي": {
        "title": "حقن وريدي (IV)",
        "notes": "عادة بالوريد الوداجي بالرقبة — يحتاج خبرة ودقة عالية، الأصعب والأخطر بين طرق الحقن. يُترك للدكتور أو الممرض المدرَّب تحديداً، مو العامل الميداني بدون إشراف.",
    },
    "حقن تحت الجلد": {
        "title": "حقن تحت الجلد (SC)",
        "notes": "الطريقة الأكثر أماناً وشيوعاً بالإدخال الميداني اليومي. ارفع الجلد بأصابعك لتشكيل \"خيمة\" (عادة برقبة الحيوان أو خلف الكتف)، أدخل الإبرة بزاوية مائلة (تقريباً 30-45 درجة) بقاعدة الخيمة الجلدية بعيداً عن العضل تحتها، وتأكد إنك تحت الجلد فعلاً (سهولة الحقن بدون مقاومة) قبل الضغط.",
    },
    "فموي": {
        "title": "فموي",
        "notes": "يُعطى مباشرة بالفم بمحقنة فموية بدون إبرة، بحذر من دخول السائل للرئة (اختناق) — ثبّت رأس الحيوان بزاوية معتدلة، مو مائلة للخلف بشدة، وأعطِ الجرعة ببطء.",
    },
    "موضعي": {
        "title": "موضعي",
        "notes": "يُوضَع مباشرة على سطح الجلد بالمكان المحدَّد (عادة خط الظهر) حسب تعليمات ملصق المنتج — تجنّب الجلد المجروح أو الملتهب.",
    },
    "رذاذ/استنشاق": {
        "title": "رذاذ/استنشاق",
        "notes": "يُستخدم عادة لعلاجات تنفسية جماعية بمساحة محدودة التهوية مؤقتاً، حسب تعليمات جهاز الرذاذ المستخدم — تأكد من تهوية المكان بعد انتهاء المدة الموصى بها.",
    },
}


def injection_guide_for(usage_method: str | None) -> dict | None:
    return INJECTION_GUIDE.get(usage_method) if usage_method else None


# دليل فئات الدواء (بند إضافي 62، 2026-07-28) — مرجع عام مختصر يشرح
# الغرض من كل فئة دواء، بنفس مبدأ INJECTION_GUIDE بالأعلى بالضبط: نص
# ثابت كتبه إنسان مرة وحدة، يُعرض بس، ما يُحسب ولا يُخترع لدواء معيّن —
# زر "ℹ️ دليل الدواء" بفورم الصيدلية يعرض هذا حسب الفئة المختارة فقط،
# وليس تشخيصاً أو توصية علاج لحيوان بعينه.
MEDICINE_CLASS_GUIDE = {
    "vaccine": {
        "title": "لقاح/تحصين",
        "notes": "يُعطى وقائياً قبل التعرّض للمرض لبناء مناعة الجسم ضده — ما يُستخدم لعلاج مرض قائم فعلاً. يحتاج عادة جرعة تنشيطية بعد مدة معيّنة (مدة الحماية) لاستمرار الوقاية.",
    },
    "antibiotic": {
        "title": "مضاد حيوي",
        "notes": "يُستخدم لعلاج عدوى بكتيرية قائمة فعلاً، بعد تشخيص الدكتور — له عادة فترة سحب قبل بيع/حلب الحيوان. ما يُجدي مع الفيروسات.",
    },
    "antiparasitic": {
        "title": "مضاد طفيليات/ديدان",
        "notes": "يُعطى دورياً حسب برنامج المزرعة لمكافحة الطفيليات الداخلية/الخارجية — التكرار المتقارب جداً بدون داعٍ قد يقلل فعاليته لاحقاً (نفس حارس منع التكرار خلال 30 يوماً بالنظام).",
    },
    "supplement": {
        "title": "فيتامينات ومكمّلات",
        "notes": "يدعم التغذية العامة أو يسدّ نقصاً غذائياً محدداً (مثل السيلينيوم) — مو علاجاً لمرض قائم، ومعظمها بدون فترة سحب.",
    },
    "topical_disinfectant": {
        "title": "مطهرات وعلاجات موضعية",
        "notes": "يُستخدم على سطح الجلد/الجرح مباشرة (تطهير، تندّب، طفيليات خارجية موضعية) — عادة أقل امتصاصاً جهازياً من الحقن/الفموي.",
    },
    "other": {
        "title": "أخرى",
        "notes": "فئة عامة لما لا يندرج تحت الفئات الأخرى — راجع ملاحظة الجرعة المرجعية المكتوبة على الدواء نفسه.",
    },
}


def medicine_class_guide_for(medicine_class: str | None) -> dict | None:
    return MEDICINE_CLASS_GUIDE.get(medicine_class) if medicine_class else None


def _withdrawal_until(event_date: date, pharmacy: Pharmacy | None) -> date | None:
    if pharmacy and pharmacy.withdrawal_days:
        return event_date + timedelta(days=pharmacy.withdrawal_days)
    return None


def _deduct_if_used(pharmacy: Pharmacy | None, quantity_used: float | None) -> None:
    if pharmacy and quantity_used:
        try:
            pharmacy.deduct_stock(quantity_used)
        except ValueError as e:
            # حظر السحب بالسالب (بند إضافي، 2026-07-23) — نعيد رفعها بنفس
            # نوع الخطأ المستخدم أصلاً لسلامة البيانات هنا، عشان تُعرض
            # بنفس آلية `except IncompleteRecordError` الموجودة بكل الشاشات
            # بدون أي تعديل عليها.
            raise IncompleteRecordError(str(e)) from e


def _check_copper_toxicity(animal_id, pharmacy: Pharmacy | None) -> None:
    """حظر نحاس سلالة النعيمي (بند إضافي 51) — **برمجي صريح بلا خيار
    تجاوز** (بقرارك)، على عكس بقية حراس هذا الملف. يمنع الحفظ كاملاً
    لو الدواء مصنَّف `contains_high_copper=True` والرأس سلالته
    "نعيمي" — النحاس آمن لمعظم السلالات بجرعات عادية لكنه سام تراكمياً
    للنعيمي تحديداً.

    **قرار متعمَّد (بند إضافي 80، 2026-08-02)**: عُرض تحويل "نعيمي" هنا
    لحقل قابل للتعديل من الواجهة (زي بقية إعدادات المزرعة) — رُفض
    صراحة. هذي القاعدة تحديداً تبقى تتطلب تعديل كود عمداً، كحاجز إضافي
    ضد تفعيل/تعطيل غير مقصود لحظر سلامة صارم. أي توسعة مستقبلية
    (سلالة ثانية حسّاسة للنحاس) تحتاج جلسة تطوير فعلية، مو تغيير إعداد."""
    if not pharmacy or not pharmacy.contains_high_copper:
        return
    from app.models import Animal
    animal = Animal.query.get(animal_id)
    if animal and animal.breed == "نعيمي":
        raise IncompleteRecordError(
            f'⛔ حظر صريح: "{pharmacy.name}" يحتوي نحاساً مرتفعاً — ممنوع استخدامه لـ'
            f'"{animal.animal_no}" (سلالة نعيمي، حساسة تراكمياً للنحاس). اختر بديلاً آمناً.'
        )


def _require_quantity_if_medicine(pharmacy: Pharmacy | None, quantity_used: float | None) -> None:
    if pharmacy and not quantity_used:
        raise IncompleteRecordError(
            f'اخترت دواء ("{pharmacy.name}") بدون تحديد الكمية المستخدمة — '
            "لازم تحدد الجرعة عشان يصح حساب التكلفة وخصم المخزون."
        )


def _computed_cost(pharmacy: Pharmacy | None, quantity_used: float | None, manual_cost: float) -> float:
    """التكلفة تُحسب تلقائياً من (الكمية × سعر الوحدة بالصيدلية) لما الاثنان
    متوفرين — تتجاوز أي قيمة يدوية مُرسَلة من النموذج عشان نضمن صحتها حتى
    لو الواجهة (JS) فشلت تحدّثها أو الطلب جا من طابور مزامنة أوف لاين قديم.
    ترجع للقيمة اليدوية بس لو الدواء غير محدد أو سعر وحدته غير مسجَّل."""
    if pharmacy and quantity_used and pharmacy.unit_price:
        return round(quantity_used * pharmacy.unit_price, 2)
    return manual_cost or 0


def record_vet_visit(*, actor_user_id, animal_id, doctor_id, date_, diagnosis,
                      pharmacy_id=None, quantity_used=None, cost=0, notes=None) -> VetVisit:
    pharmacy = Pharmacy.query.get(pharmacy_id) if pharmacy_id else None
    _check_copper_toxicity(animal_id, pharmacy)
    _require_quantity_if_medicine(pharmacy, quantity_used)
    visit = VetVisit(
        animal_id=animal_id, doctor_id=doctor_id, date=date_, diagnosis=diagnosis,
        pharmacy_id=pharmacy_id, quantity_used=quantity_used,
        cost=_computed_cost(pharmacy, quantity_used, cost), notes=notes,
        withdrawal_until=_withdrawal_until(date_, pharmacy),
    )
    _deduct_if_used(pharmacy, quantity_used)
    db.session.add(visit)
    db.session.add(AuditLog(actor_user_id=actor_user_id, action="vet_visit.create",
                             entity_type="VetVisit", details=f"animal={animal_id}"))
    db.session.commit()

    from app.core.cycle_engine import record_cycle_event
    record_cycle_event(visit.animal, "vet_visit", source_type="VetVisit", source_id=visit.id, event_date=date_)
    return visit


def record_disease(*, actor_user_id, animal_id, disease_name, date_, severity,
                    pharmacy_id=None, quantity_used=None, treatment_cost=0) -> Disease:
    pharmacy = Pharmacy.query.get(pharmacy_id) if pharmacy_id else None
    _check_copper_toxicity(animal_id, pharmacy)
    _require_quantity_if_medicine(pharmacy, quantity_used)
    disease = Disease(
        animal_id=animal_id, disease_name=disease_name, date=date_, severity=severity,
        pharmacy_id=pharmacy_id, quantity_used=quantity_used,
        treatment_cost=_computed_cost(pharmacy, quantity_used, treatment_cost),
        withdrawal_until=_withdrawal_until(date_, pharmacy),
    )
    _deduct_if_used(pharmacy, quantity_used)
    db.session.add(disease)
    db.session.add(AuditLog(actor_user_id=actor_user_id, action="disease.create",
                             entity_type="Disease", details=f"animal={animal_id}"))
    db.session.commit()

    from app.core.cycle_engine import record_cycle_event
    record_cycle_event(disease.animal, "disease", source_type="Disease", source_id=disease.id, event_date=date_)
    return disease


def record_vaccination(*, actor_user_id, animal_id, vaccine_name, date_, next_due_date=None,
                        pharmacy_id=None, quantity_used=None) -> Vaccination:
    pharmacy = Pharmacy.query.get(pharmacy_id) if pharmacy_id else None
    _check_copper_toxicity(animal_id, pharmacy)
    _require_quantity_if_medicine(pharmacy, quantity_used)
    vacc = Vaccination(
        animal_id=animal_id, vaccine_name=vaccine_name, date=date_, next_due_date=next_due_date,
        pharmacy_id=pharmacy_id, quantity_used=quantity_used,
        cost=_computed_cost(pharmacy, quantity_used, 0),
        withdrawal_until=_withdrawal_until(date_, pharmacy),
    )
    _deduct_if_used(pharmacy, quantity_used)
    db.session.add(vacc)
    db.session.add(AuditLog(actor_user_id=actor_user_id, action="vaccination.create",
                             entity_type="Vaccination", details=f"animal={animal_id}"))
    db.session.commit()

    from app.core.cycle_engine import record_cycle_event
    record_cycle_event(vacc.animal, "vaccination", source_type="Vaccination", source_id=vacc.id, event_date=date_)
    return vacc


# نطاق الحرارة الطبيعية للمجترات الصغيرة (غنم/ماعز بالغ) — مرجع عام
# موثّق (بند إضافي 127، المرحلة 2)، يُستخدم للعرض التوجيهي فقط، بدون
# أي تشخيص أو حساب جرعة. النطاق الطبيعي يتفاوت قليلاً حسب المرجع
# والعمر والحالة الفسيولوجية — رقم إرشادي عام، مو حداً طبياً قاطعاً.
NORMAL_TEMP_RANGE_C = (38.5, 40.0)


def classify_temperature(temp_c: float | None) -> str | None:
    """تصنيف نصي بسيط لدرجة حرارة مُدخَلة — عرض توجيهي بشاشة نتيجة
    التشخيص بس، لا يدخل بحساب الاحتمالات حالياً (مؤجَّل للمرحلة 3
    "معادلة الوزن الموزونة" حسب الخطة المتفَق عليها)."""
    if temp_c is None:
        return None
    low, high = NORMAL_TEMP_RANGE_C
    if temp_c < low:
        return "منخفضة عن الطبيعي"
    if temp_c > high:
        return "مرتفعة عن الطبيعي (حمى محتملة)"
    return "ضمن النطاق الطبيعي"


def animal_age_label(animal) -> str | None:
    """تسمية عمر مبسّطة (نفس منطق `animal_profile_service._age_label`،
    منسوخة هنا محلياً بدل استيراد دالة خاصة عبر وحدة ثانية) — تُعرض
    كسياق بشاشة نتيجة التشخيص، بدون أي تأثير على الترتيب حالياً."""
    if not animal or not animal.birth_date:
        return None
    days = (date.today() - animal.birth_date).days
    if days < 0:
        return None
    if days < 60:
        return f"{days} يوم"
    if days < 730:
        return f"{days // 30} شهر"
    return f"{days // 365} سنة"


def related_symptoms(primary_symptom_id: int) -> list[Symptom]:
    """شجرة القرار التشخيصية، الخطوة الثانية (بند إضافي، 2026-07-24) —
    بعد اختيار عرض رئيسي، نجمع كل الأعراض الثانوية المرتبطة بأي مرض
    يشارك نفس العرض الرئيسي (بدل عرض الثلاثين عرضاً كاملة) — هذا اللي
    يخلي الشجرة "تفاعلية" فعلاً (أسئلة متابعة ذات صلة)، مو قائمة مسطّحة."""
    disease_ids = [
        row.disease_type_id for row in
        DiseaseSymptomLink.query.filter_by(symptom_id=primary_symptom_id).all()
    ]
    if not disease_ids:
        return []
    symptom_ids = {
        row.symptom_id for row in
        DiseaseSymptomLink.query.filter(DiseaseSymptomLink.disease_type_id.in_(disease_ids)).all()
    }
    symptom_ids.discard(primary_symptom_id)
    return Symptom.query.filter(Symptom.id.in_(symptom_ids)).order_by(Symptom.name).all()


def score_diagnoses(*, symptom_ids: list[int]) -> list[dict]:
    """محرك التطابق (بند إضافي، 2026-07-24) — يجمع أوزان الأعراض
    المُدخَلة لكل مرض ويرتّبها تنازلياً. **مطابقة أنماط ضد مرجع معرفة
    عامة موثّقة، مو تشخيصاً مخبرياً مؤكَّداً** — النتيجة تبقى اقتراحاً
    يحتاج مراجعة الدكتور وإغلاقاً فعلياً بعد تعافٍ موثّق (`Disease.status`،
    قاعدة 12.3 الموجودة أصلاً)."""
    if not symptom_ids:
        return []
    links = DiseaseSymptomLink.query.filter(DiseaseSymptomLink.symptom_id.in_(symptom_ids)).all()
    scores: dict[int, dict] = {}
    for link in links:
        entry = scores.setdefault(link.disease_type_id, {"score": 0, "matched_symptoms": []})
        entry["score"] += link.weight
        entry["matched_symptoms"].append(link.symptom.name)

    results = []
    for disease_type_id, data in scores.items():
        results.append({
            "disease_type": DiseaseType.query.get(disease_type_id),
            "score": data["score"],
            "matched_symptoms": data["matched_symptoms"],
        })
    results.sort(key=lambda r: -r["score"])
    return results


def last_antiparasitic_dose(animal_id) -> date | None:
    """أحدث تاريخ جرعة مضاد طفيليات/ديدان (`Pharmacy.medicine_class ==
    "antiparasitic"`) لهذا الحيوان، عبر الجداول الثلاثة (بند إضافي 50)
    — نفس نمط تجميع `animal_under_withdrawal` بالضبط، لعدم وجود جدول
    "علاجات" موحّد."""
    candidates = []
    for model in (VetVisit, Disease, Vaccination):
        row = (
            model.query.join(Pharmacy, model.pharmacy_id == Pharmacy.id)
            .filter(model.animal_id == animal_id, Pharmacy.medicine_class == "antiparasitic")
            .order_by(model.date.desc())
            .first()
        )
        if row:
            candidates.append(row.date)
    return max(candidates) if candidates else None


def redose_guard_warning(*, animal_id, pharmacy: Pharmacy | None, redose_days: int) -> dict | None:
    """حارس منع تكرار جرعة الطفيليات خلال N يوماً (بند إضافي 50) —
    تحذير فقط يتيح للطبيب التجاوز بسبب صريح (قرارك الصريح)، مو حظراً
    نهائياً. يرجّع None لو الدواء المختار مو مصنَّفاً "مضاد طفيليات"،
    أو ما فيه جرعة سابقة خلال المدة."""
    if not pharmacy or pharmacy.medicine_class != "antiparasitic":
        return None
    last_date = last_antiparasitic_dose(animal_id)
    if not last_date:
        return None
    days_since = (date.today() - last_date).days
    if days_since >= redose_days:
        return None
    return {
        "last_date": last_date,
        "days_since": days_since,
        "message": (
            f"هذا الرأس أخذ جرعة مضاد طفيليات/ديدان قبل {days_since} يوماً فقط "
            f"({last_date}) — أقل من الحد الآمن ({redose_days} يوماً). فكّر بفحص "
            "أسباب أخرى لضعف النمو قبل التكرار، أو أدخل سبباً صريحاً للتجاوز."
        ),
    }


# بروتوكول الطوارئ والأعراض الحادة (بند إضافي 51) — أي عرض بهذي
# القائمة، لو دخل ضمن أعراض المساعد التشخيصي، يشغّل تلقائياً عزلاً
# فورياً + تنبيه تشخيص تفريقي (`check_emergency_symptoms`، تُستدعى من
# `diagnose_result`) — بمعزل عن ترتيب الاحتمالات العادي لـ
# `score_diagnoses`. النص هنا هو نفسه اسم الصف بجدول Symptom (بند
# `app/cli.py`، `DEFAULT_SYMPTOMS_PRIMARY`) — أي تعديل هنا يحتاج تعديل
# مطابق هناك.
EMERGENCY_SYMPTOMS = {
    "عمى مفاجئ / عتامة العين": {
        "differential": "اشتباه ليستريا / نقص فيتامين B1 (PEM) / التهاب ملتحمة معدٍ (Pinkeye)",
        "advice": "راجع الفحص البيطري الفوري (حرارة، توازن، ردة فعل الحدقة) والسجل العلفي (تغيّر مفاجئ بالعليقة يرفع اشتباه PEM).",
    },
}


def check_emergency_symptoms(*, animal_id, symptom_names: list[str], actor_user_id: int) -> dict | None:
    """يفحص لو أي عرض مُدخَل بشجرة القرار التشخيصية ضمن `EMERGENCY_
    SYMPTOMS` — لو فيه، يعزل الرأس فوراً (نفس منطق العزل الجماعي
    اليدوي، `bulk_service.apply_bulk_isolation`) ويرجّع تفصيل التشخيص
    التفريقي للعرض بشاشة النتيجة. اتقاء تكرار: لو الرأس أصلاً بحظيرة
    العزل، ما يُعاد النقل، بس يرجّع نفس التفصيل التفريقي."""
    matched = [EMERGENCY_SYMPTOMS[n] for n in symptom_names if n in EMERGENCY_SYMPTOMS]
    if not matched or not animal_id:
        return None

    from app.core.bulk_service import apply_bulk_isolation
    reason = " + ".join(m["differential"] for m in matched)
    results = apply_bulk_isolation(
        animal_ids=[animal_id], reason=f"بروتوكول طوارئ — {reason}",
        note_date=date.today(), actor_user_id=actor_user_id,
    )
    return {
        "isolation_result": results.get(animal_id, "-"),
        "differentials": [m["differential"] for m in matched],
        "advice": [m["advice"] for m in matched],
    }


def animal_under_withdrawal(animal_id) -> date | None:
    """أقرب تاريخ 'يصير آمن بعده البيع/الحليب' لو الحيوان تحت فترة سحب حالياً حالياً.
    تُستخدم لاحقاً كبوابة حقيقية تمنع البيع أثناء فترة السحب (مرحلة 3)."""
    today = date.today()
    candidates = []
    for model in (VetVisit, Disease, Vaccination):
        row = (model.query
               .filter(model.animal_id == animal_id, model.withdrawal_until.isnot(None), model.withdrawal_until >= today)
               .order_by(model.withdrawal_until.desc())
               .first())
        if row:
            candidates.append(row.withdrawal_until)
    return max(candidates) if candidates else None
