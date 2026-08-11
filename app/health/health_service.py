"""
منطق العمل الصحي: تسجيل زيارة/مرض/تطعيم، مع تطبيق قاعدة "فترة السحب"
تلقائياً من بيانات الدواء بالصيدلية (بدل ما تُحسب يدوياً أو تُنسى).
"""
from datetime import date, timedelta
from flask_babel import lazy_gettext as _l
from app.extensions import db
from app.models import Pharmacy, VetVisit, Disease, Vaccination, AuditLog, Symptom, DiseaseSymptomLink, DiseaseType, EmergencySymptom


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
        "title": _l("حقن عضل (IM)"),
        "notes": _l("بعضلات الرقبة الجانبية أو الفخذ الخلفي عند البالغين، بعيداً عن العمود الفقري والأعصاب الكبيرة. دوّر مكان الحقن بين الجانبين لتفادي تندّب متكرر بنفس المكان. إبرة أقصر وأدق للحملان الصغيرة."),
    },
    "حقن وريدي": {
        "title": _l("حقن وريدي (IV)"),
        "notes": _l("عادة بالوريد الوداجي بالرقبة — يحتاج خبرة ودقة عالية، الأصعب والأخطر بين طرق الحقن. يُترك للدكتور أو الممرض المدرَّب تحديداً، مو العامل الميداني بدون إشراف."),
    },
    "حقن تحت الجلد": {
        "title": _l("حقن تحت الجلد (SC)"),
        "notes": _l("الطريقة الأكثر أماناً وشيوعاً بالإدخال الميداني اليومي. ارفع الجلد بأصابعك لتشكيل \"خيمة\" (عادة برقبة الحيوان أو خلف الكتف)، أدخل الإبرة بزاوية مائلة (تقريباً 30-45 درجة) بقاعدة الخيمة الجلدية بعيداً عن العضل تحتها، وتأكد إنك تحت الجلد فعلاً (سهولة الحقن بدون مقاومة) قبل الضغط."),
    },
    "فموي": {
        "title": _l("فموي"),
        "notes": _l("يُعطى مباشرة بالفم بمحقنة فموية بدون إبرة، بحذر من دخول السائل للرئة (اختناق) — ثبّت رأس الحيوان بزاوية معتدلة، مو مائلة للخلف بشدة، وأعطِ الجرعة ببطء."),
    },
    "موضعي": {
        "title": _l("موضعي"),
        "notes": _l("يُوضَع مباشرة على سطح الجلد بالمكان المحدَّد (عادة خط الظهر) حسب تعليمات ملصق المنتج — تجنّب الجلد المجروح أو الملتهب."),
    },
    "رذاذ/استنشاق": {
        "title": _l("رذاذ/استنشاق"),
        "notes": _l("يُستخدم عادة لعلاجات تنفسية جماعية بمساحة محدودة التهوية مؤقتاً، حسب تعليمات جهاز الرذاذ المستخدم — تأكد من تهوية المكان بعد انتهاء المدة الموصى بها."),
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
        "title": _l("لقاح/تحصين"),
        "notes": _l("يُعطى وقائياً قبل التعرّض للمرض لبناء مناعة الجسم ضده — ما يُستخدم لعلاج مرض قائم فعلاً. يحتاج عادة جرعة تنشيطية بعد مدة معيّنة (مدة الحماية) لاستمرار الوقاية."),
    },
    "antibiotic": {
        "title": _l("مضاد حيوي"),
        "notes": _l("يُستخدم لعلاج عدوى بكتيرية قائمة فعلاً، بعد تشخيص الدكتور — له عادة فترة سحب قبل بيع/حلب الحيوان. ما يُجدي مع الفيروسات."),
    },
    "antiparasitic": {
        "title": _l("مضاد طفيليات/ديدان"),
        "notes": _l("يُعطى دورياً حسب برنامج المزرعة لمكافحة الطفيليات الداخلية/الخارجية — التكرار المتقارب جداً بدون داعٍ قد يقلل فعاليته لاحقاً (نفس حارس منع التكرار خلال 30 يوماً بالنظام)."),
    },
    "supplement": {
        "title": _l("فيتامينات ومكمّلات"),
        "notes": _l("يدعم التغذية العامة أو يسدّ نقصاً غذائياً محدداً (مثل السيلينيوم) — مو علاجاً لمرض قائم، ومعظمها بدون فترة سحب."),
    },
    "topical_disinfectant": {
        "title": _l("مطهرات وعلاجات موضعية"),
        "notes": _l("يُستخدم على سطح الجلد/الجرح مباشرة (تطهير، تندّب، طفيليات خارجية موضعية) — عادة أقل امتصاصاً جهازياً من الحقن/الفموي."),
    },
    "other": {
        "title": _l("أخرى"),
        "notes": _l("فئة عامة لما لا يندرج تحت الفئات الأخرى — راجع ملاحظة الجرعة المرجعية المكتوبة على الدواء نفسه."),
    },
}


def medicine_class_guide_for(medicine_class: str | None) -> dict | None:
    return MEDICINE_CLASS_GUIDE.get(medicine_class) if medicine_class else None


# دليل الأعراض الميداني السريع (بند إضافي، خطوات إسعاف أولية عامة
# لحين وصول الطبيب) — بنفس مبدأ INJECTION_GUIDE/MEDICINE_CLASS_GUIDE
# بالضبط: مرجع عام ثابت (إجراءات تشغيلية قياسية شائعة بأدلة تربية
# المجترات الصغيرة)، بدون أي جرعة دواء أو تشخيص جازم لحالة حيوان
# بعينه. الهدف: يعرف العامل الميداني "وش يسوي بالخمس دقائق الأولى"
# قبل وصول الدكتور، مو يستبدل قراره. كل بند مختوم صراحة بأنه إجراء
# أولي مؤقت وأن القرار العلاجي النهائي للطبيب حصراً.
FIELD_SYMPTOM_GUIDE = {
    "lethargy": {
        "icon": "😴",
        "title": _l("خمول / ضعف عام"),
        "first_aid": _l(
            "إجراءات أولية لحين وصول الطبيب:\n"
            "• افصل الرأس عن باقي القطيع بمكان هادئ ومظلّل، بعيد عن الزحام.\n"
            "• وفّر ماء نظيف بمتناوله مباشرة — لا تجبره على الشرب.\n"
            "• سجّل الحرارة لو عندك ميزان حرارة بيطري (تحت الذيل) — رقم فعلي يفيد الدكتور كثير.\n"
            "• لا تعطِ أي دواء أو حقنة بدون توجيه الدكتور مباشرة.\n"
            "• راقب: هل يقف ويمشي طبيعي؟ هل يستجيب لصوتك؟ سجّل أي تغيّر بالوقت."
        ),
        "urgent": False,
    },
    "diarrhea": {
        "icon": "💩",
        "title": _l("إسهال"),
        "first_aid": _l(
            "إجراءات أولية لحين وصول الطبيب:\n"
            "• اعزل الرأس فوراً — الإسهال ينتقل بسرعة بين رؤوس القطيع.\n"
            "• وفّر ماء نظيف بكثرة — خطر الجفاف أعلى خطر بالإسهال، خصوصاً بالصغار.\n"
            "• لو الإسهال مدمّى أو لونه غامق جداً أو الرأس صغير العمر (بهمة) = اتصل بالطبيب فوراً، لا تنتظر.\n"
            "• لا تعطِ أي مضاد حيوي أو دواء إسهال بدون الطبيب — أغلب حالات الإسهال البسيطة تحتاج فقط سوائل ومراقبة.\n"
            "• نظّف المكان اللي كان فيه الرأس قبل ما تدخل رؤوس ثانية."
        ),
        "urgent": True,
    },
    "refuses_food": {
        "icon": "🚫",
        "title": _l("امتناع عن الأكل"),
        "first_aid": _l(
            "إجراءات أولية لحين وصول الطبيب:\n"
            "• تأكد إن العلف والماء متوفرين وبمتناوله فعلاً (مو مشكلة وصول).\n"
            "• افحص فمه بلطف لو تقدر — جروح، تورّم، أو رغوة قد تفسّر رفض الأكل.\n"
            "• راقب مدة الامتناع — أكثر من يوم كامل بدون أكل (خصوصاً بهمة أو حامل) وضع يستدعي طبيب بلا تأجيل.\n"
            "• لا تجبره على الأكل ولا تعطِ منشّط شهية بدون الطبيب.\n"
            "• سجّل أي أعراض مصاحبة (خمول، إسهال، حرارة) — تساعد التشخيص كثير."
        ),
        "urgent": False,
    },
    "milk_change": {
        "icon": "🥛",
        "title": _l("تغيّر ملحوظ بالحليب"),
        "first_aid": _l(
            "إجراءات أولية لحين وصول الطبيب:\n"
            "• لاحظ التغيّر بدقة: كمية أقل، لون غير طبيعي، رائحة، تكتّل/دم — دوّنها.\n"
            "• افحص الضرع بلطف: احمرار، سخونة موضعية، تورّم، ألم عند اللمس = اشتباه التهاب ضرع، يحتاج طبيب قريب.\n"
            "• لا توقف الحلب أو الرضاعة الطبيعية إلا بتوجيه الدكتور — التوقف المفاجئ قد يزيد المشكلة.\n"
            "• افصل حليب هذا الرأس عن بقية الإنتاج لحين تأكيد سلامته.\n"
            "• راجع سجل الولادة الأخيرة — تغيّر الحليب قريب من الولادة أو الفطام غالباً طبيعي، بعيد عنهما يستاهل انتباه أكبر."
        ),
        "urgent": False,
    },
    "limping": {
        "icon": "🦵",
        "title": _l("عرج / صعوبة بالمشي"),
        "first_aid": _l(
            "إجراءات أولية لحين وصول الطبيب:\n"
            "• افحص القدم المتأثرة بلطف — جسم غريب، جرح، تورّم، أو حرارة موضعية.\n"
            "• أبقِه بمكان جاف ونظيف — الأرضية الموحلة أو المتّسخة تزيد التهاب القدم سوءاً.\n"
            "• لا تحاول أي علاج أو تنظيف عميق للجرح بنفسك لو كان عميقاً أو ينزف — انتظر الطبيب.\n"
            "• قلّل حركته الإجبارية (لا تنقله مسافات طويلة) لحين الفحص."
        ),
        "urgent": False,
    },
    "sudden_collapse": {
        "icon": "🆘",
        "title": _l("سقوط مفاجئ / تشنّج / عدم قدرة على الوقوف"),
        "first_aid": _l(
            "إجراءات أولية لحين وصول الطبيب — حالة تستدعي اتصال فوري بالطبيب، لا تنتظر:\n"
            "• أبعد أي شي حاد أو خطر حوله، وأعطه مساحة — لا تحاول تقييده بالقوة أثناء أي تشنّج.\n"
            "• لا تسكب أي شي بفمه (ماء أو دواء) وهو غير واعٍ تماماً — خطر اختناق حقيقي.\n"
            "• سجّل وقت بداية الحالة ومدتها لو قدرت — معلومة مهمة جداً للطبيب.\n"
            "• اتصل بالطبيب فوراً بالهاتف أيضاً بالتوازي مع رفع هذا البلاغ — هذي حالة لا تنتظر."
        ),
        "urgent": True,
    },
}


def field_symptom_guide_for(code: str | None) -> dict | None:
    return FIELD_SYMPTOM_GUIDE.get(code) if code else None


# دليل تقييم حالة الجسم (BCS) — مقياس 1-5 القياسي عالمياً للمجترات
# الصغيرة (نفس مبدأ الأدلة العامة الأخرى بالأعلى: مرجع باللمس اليدوي،
# مو قياساً رقمياً دقيقاً). كل درجة توصف بما تحسّه يدك فوق العمود
# الفقري (الفقرات القطنية) والأضلاع — أوضح وأسهل نقطتين لمس بالحقل.
BODY_CONDITION_SCALE = [
    {
        "score": 1, "label": _l("هزيل جداً"),
        "description": _l("العمود الفقري بارز وحاد جداً تحت اليد، الأضلاع واضحة بوضوح بدون أي غطاء لحمي، ما فيه أي دهن محسوس فوق أو حول الفقرات. حالة طارئة تغذوية — راجع الطبيب."),
    },
    {
        "score": 2, "label": _l("هزيل"),
        "description": _l("الفقرات القطنية محسوسة بوضوح لكن حوافها أقل حدة من الدرجة 1، الأضلاع تُحس بسهولة عند الضغط الخفيف. يحتاج تحسين خطة تغذية."),
    },
    {
        "score": 3, "label": _l("معتدل (مثالي)"),
        "description": _l("الفقرات محسوسة بضغط متوسط باليد لكن ناعمة الحواف، الأضلاع تُحس بضغط لكن ما تُرى بالعين. الوضع المستهدف لمعظم مراحل الإنتاج."),
    },
    {
        "score": 4, "label": _l("ممتلئ"),
        "description": _l("صعب تحسّس الفقرات إلا بضغط واضح، طبقة دهن ملحوظة فوق الأضلاع والقطنية. مقبول للحوامل بالثلث الأخير، مراقبة لباقي الحالات."),
    },
    {
        "score": 5, "label": _l("سمين جداً"),
        "description": _l("ما تُحس الفقرات ولا الأضلاع إطلاقاً تحت طبقة دهن سميكة، شكل الظهر مستوٍ أو مقبَّب. خطر على الولادة والحركة — يحتاج تعديل تغذية."),
    },
]


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
        from app.core.stock_alert_service import check_pharmacy_stock
        check_pharmacy_stock(pharmacy)


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


# معامل السياق (بند إضافي 127، المرحلة 3) — حرارة مرتفعة (حمى محتملة)
# ترفع احتمالية الحالات الالتهابية/المعدية بشكل عام، نفس التنبيه
# النصي اللي أضفناه بالمرحلة 2. رقم بسيط وموثَّق، مو معادلة طبية دقيقة.
FEVER_CONTEXT_MULTIPLIER = 1.15


def score_diagnoses(*, symptom_ids: list[int], temperature: float | None = None) -> list[dict]:
    """محرك التطابق (بند إضافي، 2026-07-24؛ معادلة موزونة بند إضافي 127
    المرحلة 3) — لكل مرض له عرض مطابق واحد على الأقل:
    1. `raw_score` = مجموع أوزان الأعراض المطابقة (نفس المنطق القديم،
       يبقى بحقل `score` للتوافق الخلفي).
    2. **غرامة** = مجموع أوزان أي "عرض إجباري" مرتبط بالمرض بس ما
       دخل بأعراض المستخدم.
    3. **استبعاد كامل** لو أي "عرض استبعادي" مرتبط بالمرض دخل فعلاً
       بأعراض المستخدم — المرض ما يظهر بالنتائج إطلاقاً.
    4. الناتج (بعد الغرامة) يُضرب بمعامل السياق (حمى محتملة فقط حالياً).
    5. **النسبة المئوية** = الناتج ÷ أقصى نقاط ممكنة لهذا المرض (مجموع
       أوزان *كل* أعراضه المعروفة، مو المطابقة بس) — 0-100، مقرَّبة.

    **يبقى مرجع مطابقة أنماط، مو تشخيصاً مخبرياً مؤكَّداً** — النتيجة
    اقتراح يحتاج مراجعة الدكتور وإغلاقاً فعلياً بعد تعافٍ موثّق
    (`Disease.status`، قاعدة 12.3 الموجودة أصلاً)."""
    if not symptom_ids:
        return []
    entered = set(symptom_ids)
    matched_links = DiseaseSymptomLink.query.filter(DiseaseSymptomLink.symptom_id.in_(symptom_ids)).all()
    disease_ids = {link.disease_type_id for link in matched_links}
    if not disease_ids:
        return []
    all_links = DiseaseSymptomLink.query.filter(DiseaseSymptomLink.disease_type_id.in_(disease_ids)).all()
    links_by_disease: dict[int, list] = {}
    for link in all_links:
        links_by_disease.setdefault(link.disease_type_id, []).append(link)

    context_multiplier = 1.0
    if temperature is not None and classify_temperature(temperature) == "مرتفعة عن الطبيعي (حمى محتملة)":
        context_multiplier = FEVER_CONTEXT_MULTIPLIER

    results = []
    for disease_type_id, links in links_by_disease.items():
        matched = [l for l in links if l.symptom_id in entered]
        if not matched:
            continue
        if any(l.is_exclusionary and l.symptom_id in entered for l in links):
            continue

        raw_score = sum(l.weight for l in matched)
        missing_required = [l for l in links if l.is_required and l.symptom_id not in entered]
        penalty = sum(l.weight for l in missing_required)
        adjusted = max(0, raw_score - penalty) * context_multiplier
        max_possible = sum(l.weight for l in links) or 1
        match_percent = round(min(100, (adjusted / max_possible) * 100))

        results.append({
            "disease_type": DiseaseType.query.get(disease_type_id),
            "score": raw_score,
            "match_percent": match_percent,
            "matched_symptoms": [l.symptom.name for l in matched],
            "missing_required_symptoms": [l.symptom.name for l in missing_required],
            "context_boosted": context_multiplier > 1.0,
        })
    results.sort(key=lambda r: (-r["match_percent"], -r["score"]))
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


# بروتوكول الطوارئ والأعراض الحادة (بند إضافي 51؛ صار جدولاً ديناميكياً
# بند إضافي 127 المرحلة 4) — أي عرض مسجَّل بجدول `EmergencySymptom`،
# لو دخل ضمن أعراض المساعد التشخيصي، يشغّل تلقائياً عزلاً فورياً +
# تنبيه تشخيص تفريقي (`check_emergency_symptoms`، تُستدعى من
# `diagnose_result`) — بمعزل عن ترتيب الاحتمالات العادي لـ
# `score_diagnoses`. **قائمة أسماء صريحة عمداً** (بند 121 حذّر من عزل
# مبالغ فيه لو صار تصنيفاً عاماً بدل أسماء محدَّدة) — تُدار الآن من
# `/health/emergency-symptoms` بدل تعديل كود.


def check_emergency_symptoms(*, animal_id, symptom_names: list[str], actor_user_id: int) -> dict | None:
    """يفحص لو أي عرض مُدخَل بشجرة القرار التشخيصية مسجَّل بجدول
    `EmergencySymptom` — لو فيه، يعزل الرأس فوراً (نفس منطق العزل
    الجماعي اليدوي، `bulk_service.apply_bulk_isolation`) ويرجّع تفصيل
    التشخيص التفريقي للعرض بشاشة النتيجة. اتقاء تكرار: لو الرأس أصلاً
    بحظيرة العزل، ما يُعاد النقل، بس يرجّع نفس التفصيل التفريقي."""
    if not symptom_names or not animal_id:
        return None
    matched = (
        EmergencySymptom.query.join(Symptom)
        .filter(Symptom.name.in_(symptom_names))
        .all()
    )
    if not matched:
        return None

    from app.core.bulk_service import apply_bulk_isolation
    reason = " + ".join(m.differential for m in matched)
    results = apply_bulk_isolation(
        animal_ids=[animal_id], reason=f"بروتوكول طوارئ — {reason}",
        note_date=date.today(), actor_user_id=actor_user_id,
    )

    # إشعار فوري مجاني عبر تيليجرام لكل دكتور/مالك مسجَّل (بند إضافي
    # 157) — حالة طوارئ فعلية لازم تصل لحظياً، ما تنتظر فتح التطبيق.
    from app.core import telegram_service
    from app.models import Animal, User
    animal = Animal.query.get(animal_id)
    animal_no = animal.animal_no if animal else animal_id
    for user in User.query.filter(User.telegram_chat_id.isnot(None), User.is_active_account.is_(True)).all():
        if user.has_permission("health.manage"):
            telegram_service.notify_user(
                user, f"🚨 حالة طوارئ — الرأس {animal_no}\n{reason}",
            )

    return {
        "isolation_result": results.get(animal_id, "-"),
        "differentials": [m.differential for m in matched],
        "advice": [m.advice for m in matched],
        "severities": [m.severity for m in matched],
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
