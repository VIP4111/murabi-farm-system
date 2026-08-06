"""
شاشة "التنبيهات" (بند 20 بالمواصفة الرئيسية).

نفس فلسفة صفحة تفاصيل الرأس (بند 9): ما فيه جدول "تنبيهات" منفصل يحتاج
صيانة يدوية — عرض حي يُشتق كل مرة من الجداول الفعلية، وكل تنبيه يربط
لسجله الأصلي مباشرة. حقل `alert_before_days` بـ`FarmSettings` كان موجود
من قبل بدون أي منطق يستخدمه — هذا الملف هو المنطق الناقص.

المصادر (نفس القائمة الموثّقة ببند 20، + مصدر ثامن إضافي من بند 19):
1. تطعيمات مستحقة قريباً/متأخرة (Vaccination.next_due_date)
2. فترات سحب قاربت تنتهي (withdrawal_until)
3. ولادات متوقعة قريبة (نفس منطق فلتر "قريب الولادة" ببند 8)
4. مواعيد إزالة إسفنجة/جهاز تكاثر مجدولة (ReproDevice.planned_remove_at)
5. أمراض مفتوحة من فترة بدون إغلاق
6. حيوانات "ترتيب غير منتظم" بمحرك الدورة
7. بلاغات جديدة بانتظار استلام لفترة طويلة
8. (إضافي) حيوانات جاهزة للبيع الآن حسب محرك البيع الذكي (بند 19)
9. (إضافي، بند 51) تأخر الشياع كتنبيه مستقل
10. (إضافي، بند 56) حظيرة بدون عامل مسؤول — تذكير بس، ما يمنع الحفظ
11. (إضافي، بند 65) نقص مخزون متوقّع لتحصين مجدول قريب (تقويم التحصينات،
    بند 63) — رؤوس الحظيرة الحي × الجرعة الافتراضية مقابل المخزون
12. (إضافي، بند 94) قرب انتهاء صلاحية دواء بالصيدلية (Pharmacy.expiry_date)
13. (إضافي، بند 97) تباطؤ نمو مشبوه — رأس أبطأ بوضوح من متوسط حظيرته
14. (إضافي، بند 99) مهمة متعذّرة بانتظار المراجعة — آخر 3 أيام
15. (إضافي، بند 112) عزل بدون حظيرة عزل مصنّفة — مهام isolation_check بلا حظيرة

**إضافة (2026-07-23)**: كل تنبيه صار يحمل `barn_id` (حظيرة الحيوان
المرتبط، أو حظيرة البلاغ مباشرة لو ما له حيوان محدد) — أساس شاشة
"تنبيهاتي" للعامل المسؤول عن حظائر معيّنة (`core.alerts_mine`)، بدل ما
يحتاج صلاحية `animals.view` العامة لمجرد ما يشوف تنبيهات حظائره هو.
"""
from datetime import date, timedelta
from app.models import (
    Animal, Barn, Vaccination, ReproDevice, Disease, ProductionWorkflow, Report, FarmSettings, Pharmacy,
    AnimalWeight, Task,
)


def _vaccinations_due(fs: FarmSettings) -> list[dict]:
    today = date.today()
    window_end = today + timedelta(days=fs.alert_before_days)
    rows = Vaccination.query.filter(Vaccination.next_due_date.isnot(None)).all()
    latest_by_animal = {}
    for v in rows:
        prev = latest_by_animal.get(v.animal_id)
        if prev is None or v.date > prev.date:
            latest_by_animal[v.animal_id] = v

    alerts = []
    for v in latest_by_animal.values():
        if v.next_due_date <= window_end:
            overdue = v.next_due_date < today
            alerts.append({
                "category": "تحصين", "icon": "💉",
                "label": f"{v.animal.animal_no} — {v.vaccine_name}",
                "detail": f"{'متأخر منذ' if overdue else 'مستحق بتاريخ'} {v.next_due_date}",
                "urgent": overdue, "animal_id": v.animal_id, "barn_id": v.animal.barn_id,
            })
    return alerts


def _withdrawal_ending_soon(fs: FarmSettings) -> list[dict]:
    from app.health.health_service import animal_under_withdrawal
    today = date.today()
    window_end = today + timedelta(days=fs.alert_before_days)
    alerts = []
    for a in Animal.query.filter_by(status="active").all():
        until = animal_under_withdrawal(a.id)
        if until and until <= window_end:
            alerts.append({
                "category": "فترة سحب", "icon": "⏳",
                "label": f"{a.animal_no} — تصير آمنة للبيع بتاريخ {until}",
                "detail": "", "urgent": False, "animal_id": a.id, "barn_id": a.barn_id,
            })
    return alerts


def _near_births() -> list[dict]:
    from app.core.animal_filters_service import get_filtered
    return [
        {
            "category": "ولادة متوقعة", "icon": "🍼",
            "label": f"{a.animal_no} — ولادة متوقعة قريباً",
            "detail": "", "urgent": False, "animal_id": a.id, "barn_id": a.barn_id,
        }
        for a in get_filtered("near_birth")
    ]


def _device_removal_due(fs: FarmSettings) -> list[dict]:
    today = date.today()
    window_end = today + timedelta(days=fs.alert_before_days)
    rows = ReproDevice.query.filter(
        ReproDevice.actual_remove_at.is_(None), ReproDevice.planned_remove_at.isnot(None),
    ).all()
    alerts = []
    for d in rows:
        if d.planned_remove_at <= window_end:
            overdue = d.planned_remove_at < today
            ewe = d.program.ewe if d.program else None
            alerts.append({
                "category": "جهاز تكاثر", "icon": "🔧",
                "label": f"{ewe.animal_no if ewe else '-'} — إزالة {d.device_type}",
                "detail": f"{'متأخر منذ' if overdue else 'موعد الإزالة'} {d.planned_remove_at}",
                "urgent": overdue, "animal_id": ewe.id if ewe else None,
                "barn_id": ewe.barn_id if ewe else None,
            })
    return alerts


def _stale_open_diseases(fs: FarmSettings) -> list[dict]:
    cutoff = date.today() - timedelta(days=fs.alert_before_days)
    rows = Disease.query.filter(Disease.status == "active", Disease.date <= cutoff).all()
    return [
        {
            "category": "مرض مفتوح", "icon": "🌡️",
            "label": f"{d.animal.animal_no} — {d.disease_name}",
            "detail": f"مفتوح منذ {d.date} بدون إغلاق",
            "urgent": True, "animal_id": d.animal_id, "barn_id": d.animal.barn_id,
        }
        for d in rows
    ]


def _out_of_order_animals() -> list[dict]:
    rows = ProductionWorkflow.query.filter_by(status="out_of_order").all()
    return [
        {
            "category": "ترتيب غير منتظم", "icon": "⚠️",
            "label": f"{wf.animal.animal_no} — دورة الإنتاج بترتيب غير منتظم",
            "detail": wf.missing_items or "",
            "urgent": True, "animal_id": wf.animal_id, "barn_id": wf.animal.barn_id,
        }
        for wf in rows
    ]


def _stale_new_reports(fs: FarmSettings) -> list[dict]:
    from datetime import datetime, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(hours=fs.report_stale_hours)
    rows = Report.query.filter(Report.status == "new", Report.created_at <= cutoff).all()
    return [
        {
            "category": "بلاغ منتظر", "icon": "📋",
            "label": f"بلاغ #{r.id} من {r.reporter.name if r.reporter else '-'} — بانتظار الاستلام",
            "detail": r.description[:80], "urgent": True, "animal_id": r.animal_id,
            # البلاغ ممكن يكون له حظيرة مباشرة (بلاغ عام عن حظيرة بدون حيوان
            # محدد) — نفضّلها، وإلا نرجع لحظيرة الحيوان المرتبط لو فيه.
            "barn_id": r.barn_id or (r.animal.barn_id if r.animal else None),
        }
        for r in rows
    ]


def _ready_to_sell_now() -> list[dict]:
    from app.core.smart_sale_service import get_recommendations
    return [
        {
            "category": "جاهز للبيع", "icon": "💰",
            "label": f"{row['animal'].animal_no} — {row['label']} (درجة {row['score']})",
            "detail": " — ".join(row["reasons"]), "urgent": True, "animal_id": row["animal"].id,
            "barn_id": row["animal"].barn_id,
        }
        for row in get_recommendations() if row["score"] >= 80
    ]


def _delayed_estrus(fs: FarmSettings) -> list[dict]:
    """تأخر الشياع (بند إضافي 51) — تنبيه مستقل بذاته، بدل ما يبقى
    مطموراً بمحرك البيع الذكي (بند 19) وما يظهر إلا لو درجة البيع
    وصلت 80+. يعيد استخدام منطق حساب الأيام نفسه من `smart_sale_
    service._is_reproductively_delayed` حرفياً — صفر تكرار منطق."""
    from app.core.smart_sale_service import _is_reproductively_delayed

    alerts = []
    for a in Animal.query.filter_by(status="active", gender="أنثى").all():
        if a.species != "sheep_goat":
            continue
        if _is_reproductively_delayed(a, fs):
            alerts.append({
                "category": "تأخر شياع", "icon": "🔁",
                "label": f"{a.animal_no} — تأخر حملها أكثر من {fs.female_delayed_conception_days} يوم",
                "detail": "بدون تقريع/حمل جديد منذ آخر ولادة أو تلقيح مسجَّل",
                "urgent": False, "animal_id": a.id, "barn_id": a.barn_id,
            })
    return alerts


def _barns_without_responsible_worker() -> list[dict]:
    """حظيرة بدون عامل مسؤول (بند إضافي 56) — الحقل اختياري عمداً بشاشة
    إنشاء/تعديل الحظيرة، لكن بدونه ما توجّه له أي مهام تلقائية (بند 27)
    ولا تظهر بشاشة "تنبيهاتي" لأي عامل (بند 20) — تنبيه تذكيري بس، مو
    منع حفظ، حسب قرارك الصريح."""
    rows = Barn.query.filter(Barn.responsible_worker_id.is_(None)).all()
    return [
        {
            "category": "حظيرة بدون مسؤول", "icon": "👷",
            "label": f"حظيرة {b.barn_no} ({b.barn_name}) — بدون عامل مسؤول",
            "detail": "المهام والتنبيهات التلقائية لهذي الحظيرة ما توجّه لأحد لين تحدد مسؤولاً.",
            "urgent": False, "animal_id": None, "barn_id": b.id,
        }
        for b in rows
    ]


def _upcoming_vaccination_stock_shortage(fs: FarmSettings) -> list[dict]:
    """تنبيه استباقي بنقص مخزون تحصين مجدول (بند إضافي 65) — يفحص كل
    جدولة قادمة (`VaccinationSchedule` بحالة scheduled، بند 63) ضمن
    نفس نافذة التنبيه العامة لكل هذا الملف (`FarmSettings.alert_before_days`
    — استخدمت هذا بدل رقم 7 ثابت عشان يبقى متّسقاً مع بقية التنبيهات
    وقابلاً للتعديل من إعدادات المزرعة)، ويقارن الاحتياج المتوقع (عدد
    رؤوس الحظيرة الحي × الجرعة الافتراضية المسجَّلة على اللقاح، بند 61)
    مقابل المخزون المتوفر حالياً. لو الجرعة الافتراضية غير مسجَّلة، ما
    فيه أساس رقمي للمقارنة (صفر حساب من غير رقم كتبه الدكتور) — يكتفي
    بتذكير عام بدون تقدير كمية."""
    from app.models import VaccinationSchedule
    today = date.today()
    window_end = today + timedelta(days=fs.alert_before_days)
    schedules = (VaccinationSchedule.query.filter_by(status="scheduled")
                 .filter(VaccinationSchedule.planned_date >= today,
                         VaccinationSchedule.planned_date <= window_end).all())
    alerts = []
    for s in schedules:
        head_count = s.live_head_count()
        days_left = (s.planned_date - today).days
        label = f"{s.barn.barn_name} — {s.pharmacy.name} (بعد {days_left} يوم)"
        unit = s.pharmacy.unit or ""
        if s.pharmacy.default_dose_ml and head_count:
            needed = head_count * s.pharmacy.default_dose_ml
            available = s.pharmacy.available_qty or 0
            if needed > available:
                shortage = needed - available
                alerts.append({
                    "category": "نقص مخزون تحصين مجدول", "icon": "📦",
                    "label": label,
                    "detail": (f"الاحتياج المتوقع {needed:.2f} {unit} لـ{head_count} رأس، "
                               f"والمتوفر {available:g} {unit} فقط — يوصى بشراء "
                               f"{shortage:.2f} {unit} إضافية على الأقل قبل الموعد."),
                    "urgent": days_left <= 2, "animal_id": None, "barn_id": s.barn_id,
                })
            else:
                alerts.append({
                    "category": "تذكير تحصين مجدول", "icon": "📅",
                    "label": label,
                    "detail": f"المخزون كافٍ ({available:g} {unit}) لـ{head_count} رأس — جهّز الحظيرة بالموعد.",
                    "urgent": False, "animal_id": None, "barn_id": s.barn_id,
                })
        else:
            alerts.append({
                "category": "تذكير تحصين مجدول", "icon": "📅",
                "label": label,
                "detail": f"{head_count} رأس بالحظيرة حالياً — سجّل جرعة افتراضية على الدواء لمقارنة المخزون تلقائياً.",
                "urgent": False, "animal_id": None, "barn_id": s.barn_id,
            })
    return alerts


def _medicine_expiring_soon(fs: FarmSettings) -> list[dict]:
    """قرب انتهاء صلاحية دواء (بند إضافي 94، ووسّعت لتغطية الدفعات
    ببند 96) — قبل بند 94 `Pharmacy.expiry_date` كان يُخزَّن بدون أي
    منطق تنبيه يستخدمه. بعد بند 96 (دفعات شراء منفصلة بتاريخ انتهاء
    خاص لكل دفعة، `PharmacyBatch`)، صار لازم نفحص المصدرين معاً:
    `Pharmacy.expiry_date` (الحقل القديم، لسا مدعوم لدواء ما استُخدم
    فيه فورم الشراء الجديد بعد) + أقرب تاريخ انتهاء بين دفعات لسا فيها
    مخزون فعلي (`remaining_qty > 0` — دفعة خلصت كمياتها ما تستاهل
    تنبيهاً حتى لو تاريخها قرب). نفس نافذة التنبيه العامة
    (`alert_before_days`). **نطاق متعمَّد**: دواء منتهي فعلاً (تاريخ
    بالماضي) يظهر أيضاً بنفس القائمة كـ"عاجل" — ما فيه منع استخدام
    تلقائي (قرار الدكتور يبقى قرار الدكتور)، بس التنبيه يوضّح الوضع
    بصراحة. لو الدواء الواحد له أكثر من تاريخ مقارب، يظهر بتنبيه واحد
    بس بأقرب تاريخ (مو تنبيه مكرر لكل دفعة)."""
    from app.models import PharmacyBatch
    today = date.today()
    window_end = today + timedelta(days=fs.alert_before_days)

    earliest_expiry: dict[int, date] = {}
    for p in Pharmacy.query.filter(Pharmacy.status == "active", Pharmacy.expiry_date.isnot(None)).all():
        earliest_expiry[p.id] = p.expiry_date

    for b in PharmacyBatch.query.filter(PharmacyBatch.remaining_qty > 0, PharmacyBatch.expiry_date.isnot(None)).all():
        prev = earliest_expiry.get(b.pharmacy_id)
        if prev is None or b.expiry_date < prev:
            earliest_expiry[b.pharmacy_id] = b.expiry_date

    alerts = []
    for pharmacy_id, expiry in earliest_expiry.items():
        if expiry > window_end:
            continue
        p = Pharmacy.query.get(pharmacy_id)
        if not p or p.status != "active":
            continue
        expired = expiry < today
        alerts.append({
            "category": "قرب انتهاء صلاحية دواء", "icon": "⏳",
            "label": f"{p.name} — {p.available_qty or 0:g} {p.unit or ''}",
            "detail": (f"منتهي الصلاحية منذ {today - expiry}" if expired
                       else f"تنتهي صلاحيته بتاريخ {expiry}"),
            "urgent": expired, "animal_id": None, "barn_id": None,
        })
    return alerts


FAILED_TASK_ALERT_WINDOW_DAYS = 3


def _isolation_without_barn() -> list[dict]:
    """عزل بدون حظيرة عزل مصنّفة (بند إضافي 112) — لو ما فيه أي حظيرة
    `barn_type="عزل"` وقت ولادة، `start_isolation_plan` (بند 4) كانت
    تولّد مهام العزل بدون أي حظيرة (`barn_id=None`) بصمت — الأم والمولود
    يبقون بحظيرتهم العادية، بدون أي تنبيه يخبرك إنك تحتاج تنشئ حظيرة
    عزل. هذا التنبيه يفحص العرَض المباشر: مهمة `isolation_check` مفتوحة
    بدون `barn_id` — بدل فحص "هل توجد حظيرة عزل" بشكل عام (كان يصير
    تنبيهاً دائماً حتى لمزرعة ما احتاجت عزل بعد، بدون أي فايدة فعلية)."""
    from app.models import Task
    rows = (Task.query.filter(
        Task.task_type == "isolation_check", Task.barn_id.is_(None),
        Task.status.in_(("suggested", "pending", "in_progress", "postponed")),
    ).all())
    if not rows:
        return []
    animal_ids = sorted({t.animal_id for t in rows if t.animal_id})
    return [{
        "category": "عزل بدون حظيرة مصنّفة", "icon": "🚧",
        "label": f"{len(animal_ids)} رأس بمهام عزل بدون حظيرة عزل فعلية",
        "detail": "ما فيه حظيرة بنوع \"عزل\" بالنظام — الأم والمولود ما انتقلوا فعلياً "
                  "لحظيرة عزل منفصلة عن باقي القطيع. أنشئ حظيرة جديدة بنوع \"عزل\" من "
                  "شاشة الحظائر عشان العزل التلقائي يشتغل صح للولادات الجاية.",
        "urgent": True, "animal_id": None, "barn_id": None,
    }]


def _failed_tasks_pending_review() -> list[dict]:
    """مهام متعذّرة بانتظار مراجعة (بند إضافي 99) — قبل هذا، `fail_task`
    كان يسجّل الحالة والسبب بس (`app/team/task_service.py`)، بدون أي
    أثر يذكّر أحد. مهمة تعذّرت (نقص أدوات، الحيوان مو موجود، خطر
    يمنع التنفيذ...) تبقى معلَّقة بصمت — ما فيه تصعيد ولا إعادة جدولة
    ولا حتى تنبيه يلفت نظر المالك/الدكتور لمتابعتها.

    **نطاق متعمَّد**: ما فيه آلية "تمّت المراجعة" بعد (يحتاج حقل جديد
    بـ`Task`، خارج نطاق هذا البند) — التنبيه يظهر لأي مهمة تعذّرت خلال
    آخر 3 أيام بس (`FAILED_TASK_ALERT_WINDOW_DAYS`، نافذة زمنية بدل
    تنبيه دائم بلا نهاية)، بدل تتبّع حالة مراجعة فعلية. لو احتجت متابعة
    فعلية (إعادة تعيين، إنشاء مهمة بديلة)، يبقى قرار وإجراء يدوي من
    المالك."""
    from datetime import datetime, timezone
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=FAILED_TASK_ALERT_WINDOW_DAYS)
    rows = (Task.query.filter(Task.status == "failed", Task.failed_at.isnot(None))
            .filter(Task.failed_at >= cutoff).all())
    return [
        {
            "category": "مهمة متعذّرة بانتظار المراجعة", "icon": "🚫",
            "label": f"{t.title} — {t.failure_reason or 'سبب غير محدد'}",
            "detail": (t.completion_note or "").strip() or "بدون ملاحظة إضافية من العامل.",
            "urgent": True, "animal_id": t.animal_id, "barn_id": t.barn_id,
        }
        for t in rows
    ]


WEIGHT_TREND_WINDOW_DAYS = 90
WEIGHT_TREND_MIN_COHORT = 3
WEIGHT_TREND_RATIO_THRESHOLD = 0.5


def _weight_gain_underperformers() -> list[dict]:
    """كشف مبكر لتباطؤ نمو مشبوه (بند إضافي 97) — قبل هذا، سجلات الوزن
    (`AnimalWeight`) كانت تُستخدم بس لعرض السجل التاريخي وحساب FCR/جاهزية
    البيع، بدون أي مقارنة بين الرؤوس تكشف مشكلة صحية مبكرة قبل ما تظهر
    أعراضها. الفكرة: رأس معدل زيادة وزنه أبطأ بوضوح من رفاقه بنفس
    الحظيرة (تغذية/بيئة مشتركة تقريباً) مؤشر مبكر حقيقي (طفيليات، مرض
    مبكر، مشكلة تغذية فردية) — بدون أي بيانات جديدة تحتاج إدخالها
    يدوياً، كلها مستنتجة من سجلات الوزن الموجودة أصلاً.

    **نطاق متعمَّد** (قيم اجتهادية موثّقة بالثوابت أعلى الدالة، قابلة
    للتعديل لاحقاً لو أعطيتني أرقام حقيقية): نافذة المقارنة آخر 90 يوم
    (`WEIGHT_TREND_WINDOW_DAYS`)، أقل حظيرة تُقارَن فيها الرؤوس 3 رؤوس
    عندها بيانات كافية (`WEIGHT_TREND_MIN_COHORT`، تفادياً لمقارنة رأس
    وحيد بنفسه)، وحد التنبيه معدل نمو الرأس أقل من 50% من متوسط حظيرته
    (`WEIGHT_TREND_RATIO_THRESHOLD`). رأس ينقص وزنه فعلياً (معدل سالب)
    يُعتبر "عاجل" دايماً بغض النظر عن حظيرته."""
    window_start = date.today() - timedelta(days=WEIGHT_TREND_WINDOW_DAYS)
    rows = (AnimalWeight.query.join(Animal)
            .filter(Animal.status == "active", AnimalWeight.date >= window_start)
            .order_by(AnimalWeight.animal_id, AnimalWeight.date).all())

    by_animal: dict[int, list[AnimalWeight]] = {}
    for w in rows:
        by_animal.setdefault(w.animal_id, []).append(w)

    rate_by_animal: dict[int, float] = {}
    animal_by_id: dict[int, Animal] = {}
    for animal_id, weights in by_animal.items():
        if len(weights) < 2:
            continue
        first, last = weights[0], weights[-1]
        days = (last.date - first.date).days
        if days <= 0:
            continue
        rate_by_animal[animal_id] = (last.weight - first.weight) / days
        animal_by_id[animal_id] = first.animal

    by_barn: dict[int, list[int]] = {}
    for animal_id, animal in animal_by_id.items():
        if animal.barn_id:
            by_barn.setdefault(animal.barn_id, []).append(animal_id)

    alerts = []
    for barn_id, animal_ids in by_barn.items():
        if len(animal_ids) < WEIGHT_TREND_MIN_COHORT:
            continue
        barn_avg = sum(rate_by_animal[a] for a in animal_ids) / len(animal_ids)
        if barn_avg <= 0:
            continue  # الحظيرة كلها بلا نمو موجب — ما فيه مرجع مقارنة موثوق
        for animal_id in animal_ids:
            rate = rate_by_animal[animal_id]
            losing_weight = rate < 0
            underperforming = 0 <= rate < barn_avg * WEIGHT_TREND_RATIO_THRESHOLD
            if not (losing_weight or underperforming):
                continue
            animal = animal_by_id[animal_id]
            alerts.append({
                "category": "تباطؤ نمو مشبوه", "icon": "📉",
                "label": f"{animal.animal_no} — معدل نموه {rate:.2f} كجم/يوم",
                "detail": (f"ينقص وزنه فعلياً (متوسط حظيرته {barn_avg:.2f} كجم/يوم) — يوصى بفحص صحي عاجل"
                           if losing_weight else
                           f"أبطأ بوضوح من متوسط حظيرته ({barn_avg:.2f} كجم/يوم) — يوصى بفحص صحي"),
                "urgent": losing_weight, "animal_id": animal_id, "barn_id": barn_id,
            })
    return alerts


def get_alerts(barn_ids: list[int] | None = None) -> list[dict]:
    """
    `barn_ids=None` (الافتراضي، سلوك بند 20 الأصلي بدون تغيير): كل
    التنبيهات بالمزرعة، لأي شاشة تستخدم `animals.view`. `barn_ids=[..]`:
    فلترة لتنبيهات حظائر محددة بس — أساس شاشة "تنبيهاتي" للعامل
    المسؤول عن حظيرة (`core.alerts_mine`).
    """
    fs = FarmSettings.get()

    # محرك القواعد الطبية/التغذوية الذكي (بند إضافي 51) — نفس فلسفة
    # هذا الملف بالضبط (فحص حي عند فتح الشاشة، بدون Cron)، بس هذين
    # الاثنين ينشئان صف Task فعلي (مو تنبيهاً عابراً) عند الاستحقاق.
    from app.core import pregnancy_care_service
    pregnancy_care_service.generate_late_pregnancy_tasks()

    # مهام يومية تلقائية (بند إضافي 55.1) — نفس الفلسفة بالضبط.
    from app.core import daily_task_service
    daily_task_service.generate_daily_husbandry_tasks()

    # مهام وجبات العلف حسب جدول كل حظيرة (بند إضافي 131) — نفس الفلسفة.
    from app.core import feeding_schedule_service
    feeding_schedule_service.generate_feeding_tasks()

    alerts = (
        _vaccinations_due(fs) + _withdrawal_ending_soon(fs) + _near_births()
        + _device_removal_due(fs) + _stale_open_diseases(fs) + _out_of_order_animals()
        + _stale_new_reports(fs) + _ready_to_sell_now() + _delayed_estrus(fs)
        + _barns_without_responsible_worker() + _upcoming_vaccination_stock_shortage(fs)
        + _medicine_expiring_soon(fs) + _weight_gain_underperformers()
        + _failed_tasks_pending_review() + _isolation_without_barn()
    )
    if barn_ids is not None:
        allowed = set(barn_ids)
        alerts = [a for a in alerts if a.get("barn_id") in allowed]
    alerts.sort(key=lambda a: not a["urgent"])
    return alerts
