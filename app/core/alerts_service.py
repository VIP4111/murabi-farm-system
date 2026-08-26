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
import calendar
from datetime import date, timedelta
from app.models import (
    Animal, Barn, Vaccination, ReproDevice, Disease, ProductionWorkflow, Report, FarmSettings, Pharmacy,
    AnimalWeight, Task,
)

PAYROLL_MONTH_END_REMINDER_DAYS = 3


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


def _stalled_workflow(fs: FarmSettings) -> list[dict]:
    """رأس واقف عند نفس مرحلة دورة الإنتاج بدون أي تقدّم لفترة أطول من
    `workflow_stall_alert_days` (بند إضافي 209) — قبل هذا البند، بيانات
    "متطلبات ناقصة للانتقال" كانت تظهر بس لو دخلت صفحة الرأس بنفسك،
    صفر تنبيه استباقي بشاشة "التنبيهات" العامة. `updated_at` يتحرّك
    فقط لما `evaluate()` يغيّر شي فعلياً بالصف (مرحلة/حالة/نواقص) —
    مؤشر موثوق لآخر تقدّم حقيقي، مو مجرد آخر فتح للصفحة."""
    from datetime import datetime, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(days=fs.workflow_stall_alert_days)
    rows = (ProductionWorkflow.query
            .filter(ProductionWorkflow.status == "active", ProductionWorkflow.missing_items.isnot(None))
            .all())
    alerts = []
    for wf in rows:
        updated = wf.updated_at
        if updated and updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        if updated and updated <= cutoff:
            days_stuck = (datetime.now(timezone.utc) - updated).days
            alerts.append({
                "category": "توقّف بدورة الإنتاج", "icon": "⏸️",
                "label": f"{wf.animal.animal_no} — واقف بمرحلة '{wf.stage_name}' منذ {days_stuck} يوم",
                "detail": wf.missing_items.replace("|", "؛ "),
                "urgent": days_stuck >= fs.workflow_stall_alert_days * 2,
                "animal_id": wf.animal_id, "barn_id": wf.animal.barn_id,
            })
    return alerts


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


def _incomplete_animal_data() -> list[dict]:
    """بيانات ناقصة (بند إضافي 135، فُصِّلت لكل حقل بند إضافي 138) —
    الحفظ يبقى بدون أي شرط (قرارك الصريح: خلني أسجل عادي)، بس أي رأس
    ناقص حقل مهم (جنس/وزن/غرض، + سعر للشراء/الهدية/الرصيد الافتتاحي
    بس، مو المولود) يطلع له تنبيه مستقل لكل حقل ناقص لحاله (قرارك
    الصريح: "وزّع هذا التنبيه لعدة تنبيهات... قسمه على حسب المذكور
    فيه") — بدل تنبيه واحد يجمع كل النواقص بنص واحد طويل. نفس منطق
    `data_completeness_service.missing_fields` بالضبط، مكان واحد بس
    للفحص."""
    from app.core import data_completeness_service as dcs

    alerts = []
    for a in Animal.query.filter_by(status="active").all():
        missing = dcs.missing_fields(a)
        for field in missing:
            alerts.append({
                "category": "بيانات ناقصة", "icon": "📋",
                "label": f"{a.animal_no} — ناقص: {dcs.FIELD_LABELS_AR[field]}",
                "detail": "أكمّل هذا الحقل من شاشة تعديل الحيوان.",
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


def _payroll_month_end_reminder() -> list[dict]:
    """تذكير رواتب آخر كل شهر (بند إضافي 246، طلبك الصريح: "احتاج
    تنبيه برواتب كل اخر شهر مع تأكيد لو فيه خصومات على العامل") — نفس
    فلسفة هذا الملف بالضبط (فحص حي عند فتح شاشة التنبيهات، بدون Cron).
    يبان فقط خلال آخر `PAYROLL_MONTH_END_REMINDER_DAYS` أيام من الشهر
    الحالي (أو أي وقت بعده لو الشهر خلص وراتب العامل لسا ما تأكَّد)،
    لكل عضو فريق نشط له راتب أساسي مسجَّل (`User.base_salary`) وما
    عنده راتب مؤكَّد لهذا الشهر بعد. لو فيه مسودة موجودة وفيها خصومات،
    التفصيل يذكرها صراحةً — التأكيد الفعلي بوجود خصومات نفسه يصير
    كتحذير إضافي بشاشة تجهيز الراتب نفسها (`payroll_prepare.html`)،
    مو هنا."""
    from app.models import Payroll, User
    today = date.today()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    is_near_month_end = today.day >= days_in_month - PAYROLL_MONTH_END_REMINDER_DAYS + 1
    if not is_near_month_end:
        return []

    alerts = []
    workers = User.query.filter(User.is_active_account == True, User.base_salary.isnot(None)).all()  # noqa: E712
    for w in workers:
        payroll = Payroll.query.filter_by(user_id=w.id, year=today.year, month=today.month).first()
        if payroll and payroll.status == "confirmed":
            continue
        if payroll and payroll.total_deductions > 0:
            detail = (f"فيه مسودة راتب محفوظة عليها خصومات بقيمة "
                      f"{payroll.total_deductions:.2f} — راجعها قبل التأكيد.")
        else:
            detail = "لسا ما تجهَّز راتب هذا الشهر له."
        alerts.append({
            "category": "تذكير رواتب نهاية الشهر", "icon": "💰",
            "label": f"راتب {w.name} — {today.month}/{today.year}",
            "detail": detail,
            "urgent": today.day == days_in_month, "animal_id": None, "barn_id": None,
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


def _barn_physiology_target_missing() -> list[dict]:
    """حظيرة هدف ناقصة لآلية "فرز الحظائر حسب الحالة الفسيولوجية" (بند
    إضافي 216) — `barn_physiology_service.generate_barn_move_tasks` كانت
    تتجاهل بصمت أي رأس محتاج حظيرة "حامل - الشهور الأخيرة"/"رضاعة" لو
    ما فيه حظيرة بهذا النوع أصلاً، بدون أي تنبيه يخبرك إنك تحتاج تنشئها
    — نفس مبدأ `_isolation_without_barn` أعلاه بالضبط، لنفس نوع الفجوة.

    وسّعتها ببند إضافي 217 لتغطي حظيرة "حوامل" كمان — نفس الفجوة بالضبط
    كانت موجودة بمهمة "نقل لحظيرة الحوامل" (`_move_to_pregnant_barn`)،
    واكتُشفت بفحص شامل لكل الأماكن اللي فيها نفس نمط "تجاهل صامت لسجل
    ناقص"."""
    from app.core import barn_physiology_service as bps

    today = date.today()
    targets = {
        "حامل - الشهور الأخيرة": bps._late_pregnancy_animal_ids(today),
        "رضاعة": bps._nursing_animal_ids(today),
    }
    alerts = []
    for target_barn_type, animal_ids in targets.items():
        if not animal_ids:
            continue
        if Barn.query.filter_by(barn_type=target_barn_type).first():
            continue
        alerts.append({
            "category": "حظيرة هدف ناقصة", "icon": "🏚️",
            "label": f"{len(animal_ids)} رأس بحاجة حظيرة \"{target_barn_type}\" — ما أنشأتها بعد",
            "detail": f"أنشئ حظيرة بنوع \"{target_barn_type}\" من شاشة الحظائر، عشان النظام "
                      "يقدر يقترح نقل هالرؤوس تلقائياً (بانتظار موافقة الدكتور دائماً).",
            "urgent": False, "animal_id": None, "barn_id": None,
        })

    open_pregnant_move_tasks = Task.query.filter(
        Task.task_type == "move_to_pregnant_barn",
        Task.status.in_(("suggested", "pending", "in_progress")),
    ).count()
    if open_pregnant_move_tasks and not Barn.query.filter_by(barn_type="حوامل").first():
        alerts.append({
            "category": "حظيرة هدف ناقصة", "icon": "🏚️",
            "label": f"{open_pregnant_move_tasks} مهمة \"نقل لحظيرة الحوامل\" بانتظار حظيرة \"حوامل\" غير موجودة",
            "detail": "أنشئ حظيرة بنوع \"حوامل\" من شاشة الحظائر — بدونها المهمة ما تقدر تنقل الرأس فعلياً "
                      "لما تُنجَز (تقدر تختار حظيرة بديلة يدوياً وقت الإنجاز لو ما تبي تنشئ هذا النوع).",
            "urgent": False, "animal_id": None, "barn_id": None,
        })
    return alerts


def _weight_schedule_missing_reference_date() -> list[dict]:
    """رأس مستثنى بصمت من جدولة "أوزان متأخرة" (بند إضافي 217، اكتشف
    بفحص شامل) — `scheduled_care_service.generate_overdue_weight_tasks`
    تحتاج تاريخاً مرجعياً (آخر وزن، أو ولادة/شراء/دخول لو ما فيه وزن
    أصلاً) عشان تحسب "من متى ما اتوزن" — لو الرأس ما عنده أي وزن مسجَّل
    ولا أي تاريخ من الثلاثة، الدالة تتجاهله للأبد بصمت، بدون أي تنبيه."""
    animals = Animal.query.filter_by(status="active", species="sheep_goat").all()
    missing = [
        a for a in animals
        if not AnimalWeight.query.filter_by(animal_id=a.id).first()
        and not (a.birth_date or a.purchase_date or a.entry_date)
    ]
    if not missing:
        return []
    return [{
        "category": "بيانات ناقصة", "icon": "⚖️",
        "label": f"{len(missing)} رأس ما راح يدخل جدولة الأوزان المتأخرة إطلاقاً",
        "detail": "ما عندها وزن مسجَّل ولا تاريخ ولادة/شراء/دخول — بدون أي تاريخ مرجعي، "
                  "النظام ما يقدر يحسب \"من متى ما اتوزنت\"، فتنبيه الوزن المتأخر ما يشتغل "
                  "لها أبداً. أكمّل تاريخ الشراء/الدخول أو سجّل وزناً أول من شاشة تعديل الحيوان.",
        "urgent": False, "animal_id": None, "barn_id": None,
    }]


def _isolation_without_barn() -> list[dict]:
    """عزل بدون حظيرة عزل مصنّفة (بند إضافي 112) — لو ما فيه أي حظيرة
    `barn_type="عزل"` وقت ولادة، `start_isolation_plan` (بند 4) كانت
    تولّد مهام العزل بدون أي حظيرة (`barn_id=None`) بصمت — الأم والمولود
    يبقون بحظيرتهم العادية، بدون أي تنبيه يخبرك إنك تحتاج تنشئ حظيرة
    عزل. هذا التنبيه يفحص العرَض المباشر: مهمة `isolation_check` مفتوحة
    بدون `barn_id` — بدل فحص "هل توجد حظيرة عزل" بشكل عام (كان يصير
    تنبيهاً دائماً حتى لمزرعة ما احتاجت عزل بعد، بدون أي فايدة فعلية)."""
    from app.models import Task
    alerts = []
    rows = (Task.query.filter(
        Task.task_type == "isolation_check", Task.barn_id.is_(None),
        Task.status.in_(("suggested", "pending", "in_progress", "postponed")),
    ).all())
    if rows:
        animal_ids = sorted({t.animal_id for t in rows if t.animal_id})
        alerts.append({
            "category": "عزل بدون حظيرة مصنّفة", "icon": "🚧",
            "label": f"{len(animal_ids)} رأس بمهام عزل بدون حظيرة عزل فعلية",
            "detail": "ما فيه حظيرة بنوع \"عزل\" بالنظام — الأم والمولود ما انتقلوا فعلياً "
                      "لحظيرة عزل منفصلة عن باقي القطيع. أنشئ حظيرة جديدة بنوع \"عزل\" من "
                      "شاشة الحظائر عشان العزل التلقائي يشتغل صح للولادات الجاية.",
            "urgent": True, "animal_id": None, "barn_id": None,
        })

    # امتداد بند إضافي 217 — نفس الفجوة بالضبط عند الإجهاض:
    # `isolation_service.record_abortion` تعزل الرأس فقط لو فيه حظيرة
    # "عزل" فعلياً، وإلا تتركه بحظيرته العادية بصمت (بدون barn_id=None
    # بمهمة العينات، فالفحص أعلاه ما يلتقطها) — نتحقق مباشرة من وجود
    # مهام "سحب عيّنات إجهاض" مفتوحة بدون حظيرة عزل موجودة أصلاً.
    abortion_rows = Task.query.filter(
        Task.task_type == "abortion_sampling",
        Task.status.in_(("suggested", "pending", "in_progress", "postponed")),
    ).all()
    if abortion_rows and not Barn.query.filter_by(barn_type="عزل").first():
        animal_ids2 = sorted({t.animal_id for t in abortion_rows if t.animal_id})
        alerts.append({
            "category": "عزل بدون حظيرة مصنّفة", "icon": "🚧",
            "label": f"{len(animal_ids2)} رأس أجهض بدون عزل فعلي — ما فيه حظيرة عزل",
            "detail": "ما فيه حظيرة بنوع \"عزل\" بالنظام — الرأس المُجهِض ما انتقل لعزل طبي "
                      "منفصل ولسا يخالط باقي القطيع رغم احتمال عدوى. أنشئ حظيرة بنوع \"عزل\" "
                      "من شاشة الحظائر ثم انقل الرأس يدوياً.",
            "urgent": True, "animal_id": None, "barn_id": None,
        })

    return alerts


def _feed_distribution_shortage() -> list[dict]:
    """توزيع علف تلقائي فشل جزئياً/كلياً (بند إضافي 220) — قبل هذا
    البند، `task_service._distribute_barn_feed` كانت تكتب سبب عدم
    الخصم بملاحظة إنجاز المهمة بس (نص مدفون، لازم تفتح المهمة بنفسك
    تشوفه) — المهمة نفسها تنجز عادي بدون أي إشارة بالواجهة الرئيسية
    إن العلف ما اتوزّع فعلياً. هذا التنبيه يفحص العرَض المباشر: مهمة
    "وجبة علف" منجزة خلال آخر `FAILED_TASK_ALERT_WINDOW_DAYS` أيام
    وملاحظتها فيها ⚠️ (نفس الرمز اللي تكتبه `_distribute_barn_feed`
    دائماً عند أي نقص) — نفس نافذة زمنية `_failed_tasks_pending_review`
    بالضبط، لنفس السبب (ما فيه حقل "تمّت المراجعة" بعد)."""
    from datetime import datetime, timezone
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=FAILED_TASK_ALERT_WINDOW_DAYS)
    rows = (Task.query.filter(
        Task.task_type == "feeding_schedule", Task.status == "done",
        Task.completed_at.isnot(None), Task.completed_at >= cutoff,
        Task.completion_note.isnot(None), Task.completion_note.contains("⚠️"),
    ).all())
    return [
        {
            "category": "توزيع علف ناقص", "icon": "🥣",
            "label": f"{t.title} — العلف ما اتوزّع بالكامل",
            "detail": (t.completion_note or "").strip(),
            "urgent": True, "animal_id": t.animal_id, "barn_id": t.barn_id,
        }
        for t in rows
    ]


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


SUGGESTED_TASK_ALERT_MIN_AGE_HOURS = 24


def _suggested_tasks_pending_approval() -> list[dict]:
    """مهام مقترحة بانتظار الاعتماد (بند إضافي 233) — طلبك: "ليش موب
    طالعين لي بالتنبيهات". قبل هذا، شاشة "مهام مقترحة" كانت شاشة
    منفصلة تماماً عن التنبيهات — لو حد ما فتحها بنفسه بمبادرة منه،
    تراكم مهام (تنظيف/تحصين/رش وقائي...) بانتظار اعتماد بدون أي تذكير
    بأي مكان ثاني بالنظام. نطاق متعمَّد: بس المهام اللي عدّت
    `SUGGESTED_TASK_ALERT_MIN_AGE_HOURS` (افتراضي يوم) بدون اعتماد —
    مو أي مهمة تولّدت قبل دقايق، عشان الدكتور يعطى فرصة طبيعية يراجعها
    أول قبل ما تُحسب "متأخرة"."""
    from datetime import datetime, timezone
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=SUGGESTED_TASK_ALERT_MIN_AGE_HOURS)
    rows = (Task.query.filter(Task.status == "suggested", Task.created_at.isnot(None))
            .filter(Task.created_at <= cutoff).all())
    return [
        {
            "category": "مهمة مقترحة بانتظار الاعتماد", "icon": "📥",
            "label": f"{t.title} — بانتظار اعتمادك من قبل {t.created_at.date()}",
            "detail": "افتح شاشة \"مهام مقترحة بانتظار الاعتماد\" واعتمدها أو أجّلها أو احذفها.",
            "urgent": False, "animal_id": t.animal_id, "barn_id": t.barn_id,
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


def vaccination_counts() -> tuple[int, int]:
    """(متأخرة، قادمة) — آخر تطعيم مسجَّل لكل رأس عنده `next_due_date`
    (بند إضافي 209، لبطاقة "التطعيمات" بالرئيسية). بلا نافذة زمنية
    (`alert_before_days`) خلافاً لـ`_vaccinations_due` — هنا العدد
    الكامل لكل شي "لم يحن وقته بعد" مهما بعُد تاريخه، مو بس القريب."""
    today = date.today()
    rows = Vaccination.query.filter(Vaccination.next_due_date.isnot(None)).all()
    latest_by_animal = {}
    for v in rows:
        prev = latest_by_animal.get(v.animal_id)
        if prev is None or v.date > prev.date:
            latest_by_animal[v.animal_id] = v
    overdue = sum(1 for v in latest_by_animal.values() if v.next_due_date < today)
    upcoming = sum(1 for v in latest_by_animal.values() if v.next_due_date >= today)
    return overdue, upcoming


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
    # كشف حمل ضمني (بند إضافي 236) — نفس نقطة الاستدعاء بالضبط.
    pregnancy_care_service.detect_implicit_pregnancies()

    # مهام يومية تلقائية (بند إضافي 55.1) — نفس الفلسفة بالضبط.
    from app.core import daily_task_service
    daily_task_service.generate_daily_husbandry_tasks()

    # مهام وجبات العلف حسب جدول كل حظيرة (بند إضافي 131) — نفس الفلسفة.
    from app.core import feeding_schedule_service
    feeding_schedule_service.generate_feeding_tasks()

    # فرز الحظائر حسب الحالة الفسيولوجية (بند إضافي 133) — نفس الفلسفة.
    from app.core import barn_physiology_service
    barn_physiology_service.generate_barn_move_tasks()

    # بيانات ناقصة (بند إضافي 135) — نفس الفلسفة.
    from app.core import data_completeness_service
    data_completeness_service.generate_completion_tasks()

    # مهام ذكية من مصادر ثانية غير العزل — تطعيمات مستحقة عامة وأوزان
    # متأخرة (بند إضافي 149) — نفس الفلسفة.
    from app.core import scheduled_care_service
    scheduled_care_service.generate_vaccination_due_tasks()
    scheduled_care_service.generate_overdue_weight_tasks()

    # صيانة أصول مستحقة (بند إضافي 186) — نفس الفلسفة.
    from app.core import asset_maintenance_service
    asset_maintenance_service.generate_maintenance_due_tasks()

    # رادار كشف تكرار الحالات المرضية بالحظيرة (بند إضافي 188) — نفس الفلسفة.
    from app.core import outbreak_service
    outbreak_service.detect_barn_clusters()

    alerts = (
        _vaccinations_due(fs) + _withdrawal_ending_soon(fs) + _near_births()
        + _device_removal_due(fs) + _stale_open_diseases(fs) + _out_of_order_animals()
        + _stale_new_reports(fs) + _ready_to_sell_now() + _delayed_estrus(fs)
        + _barns_without_responsible_worker() + _upcoming_vaccination_stock_shortage(fs)
        + _medicine_expiring_soon(fs) + _weight_gain_underperformers()
        + _failed_tasks_pending_review() + _isolation_without_barn()
        + _incomplete_animal_data() + _stalled_workflow(fs)
        + _barn_physiology_target_missing() + _weight_schedule_missing_reference_date()
        + _feed_distribution_shortage() + _suggested_tasks_pending_approval()
        + _payroll_month_end_reminder()
    )
    if barn_ids is not None:
        allowed = set(barn_ids)
        alerts = [a for a in alerts if a.get("barn_id") in allowed]
    alerts.sort(key=lambda a: not a["urgent"])
    return alerts


# رابط "حل المشكلة" لكل فئة تنبيه (بند إضافي 222) — بطلبك الصريح:
# "زر يحولني لموقع كل مشكلة على حدا". مو كل فئة عندها شاشة حل مباشرة
# (بعضها معلوماتي بحت زي "فترة سحب" — تنتهي لحالها، ما فيه إجراء)،
# فالفئات الناقصة من هالخريطة عمداً تبقى بدون زر (تفصيلها النصي يبقى
# كافياً). كل دالة تاخذ animal_id وترجع endpoint + kwargs لـ`url_for`.
_ALERT_ACTION_ROUTES = {
    "تحصين": lambda aid: ("health.vaccinations_new", {}),
    "مرض مفتوح": lambda aid: ("health.diseases_list", {}),
    "بيانات ناقصة": lambda aid: ("core.animals_edit", {"animal_id": aid}),
    "ترتيب غير منتظم": lambda aid: ("core.animal_workflow", {"animal_id": aid}),
    "توقّف بدورة الإنتاج": lambda aid: ("core.animal_workflow", {"animal_id": aid}),
    "جاهز للبيع": lambda aid: ("core.animal_workflow", {"animal_id": aid, "_anchor": "exit"}),
    "تأخر شياع": lambda aid: ("repro.programs_list", {}),
    "جهاز تكاثر": lambda aid: ("repro.programs_list", {}),
    "تباطؤ نمو مشبوه": lambda aid: ("core.animals_edit", {"animal_id": aid}),
    "مهمة مقترحة بانتظار الاعتماد": lambda aid: ("team.tasks_list", {"_anchor": "suggested-tasks"}),
    "تذكير رواتب نهاية الشهر": lambda aid: ("team.payroll_list", {}),
}


def alert_action_url(alert: dict) -> str | None:
    """رابط "حل هذي المشكلة" لتنبيه واحد — يستخدم `_ALERT_ACTION_ROUTES`
    أعلاه. يرجّع None لو الفئة ما عندها إجراء مباشر (تبقى معلوماتية)."""
    from flask import url_for
    resolver = _ALERT_ACTION_ROUTES.get(alert.get("category"))
    if not resolver:
        return None
    endpoint, kwargs = resolver(alert.get("animal_id"))
    return url_for(endpoint, **kwargs)


def alerts_for_animal(animal_id: int) -> list[dict]:
    """كل تنبيهات رأس واحد بالتفصيل (بند إضافي 221) — الزر ⚠️ برقم
    بسجل الحيوانات كان يوديك لصفحة تفاصيل الرأس بدون أي قائمة توضّح
    شنو بالضبط التنبيهات، فتضطر تدوّر بنفسك. هذي تُستخدم بأعلى صفحة
    تفاصيل الرأس لعرض كل تنبيه بعنوانه وتفصيله صراحة، بدل ما يبقى
    مجرد رقم. كل تنبيه يرجع ومعه `action_url` (بند إضافي 222) —
    رابط مباشر لشاشة حل تلك المشكلة بالذات، لو موجودة."""
    rows = [a for a in get_alerts() if a.get("animal_id") == animal_id]
    for a in rows:
        a["action_url"] = alert_action_url(a)
    return rows


def alert_counts_by_animal() -> dict:
    """عدد التنبيهات لكل رأس على حدة (بند إضافي 214) — لعمود "التنبيهات"
    بسجل الحيوانات وفقعة إجمالي التنبيهات على زر "الحيوانات" بالرئيسية.
    يعيد استخدام `get_alerts()` نفسها (كل التنبيهات مربوطة أصلاً بـ
    `animal_id` لو تخص رأساً محدداً)، بدل بناء منطق تجميع مستقل."""
    counts: dict[int, int] = {}
    for a in get_alerts():
        animal_id = a.get("animal_id")
        if animal_id:
            counts[animal_id] = counts.get(animal_id, 0) + 1
    return counts


# ---------- تنبيهات سياقية فورية (Contextual Triggered Notifications) ----------
# بند إضافي 230: بعد إتمام إجراء بصفحة 1، هل فيه شي بصفحة 2 يستاهل
# مراجعة فورية؟ نفس نافذة `alert_before_days` المستخدمة بكل دوال هذا
# الملف — ما فيه شرط "متى نعتبره مستحق قريباً" مستقل، مصدر واحد للحقيقة.

def vaccination_followup_toast(animal_id: int) -> dict | None:
    """بعد ما يسجّل المستخدم تطعيم فعلي لرأس (صفحة 1: `health.vaccinations_new`)،
    نتحقق هل فيه موعد بجدول التحصينات المجدولة (`VaccinationSchedule`)
    لنفس حظيرة الرأس مستحق قريباً بعد (نفس نافذة `alert_before_days`).
    لو فيه، نرجّع بيانات Toast يوجّه لصفحة "جدول التحصينات" (صفحة 2)
    مباشرة، بدل ما ينتظر المستخدم يوصله شاشة التنبيهات العامة لاحقاً."""
    from app.models import VaccinationSchedule
    animal = Animal.query.get(animal_id)
    if not animal or not animal.barn_id:
        return None
    fs = FarmSettings.query.first()
    window_end = date.today() + timedelta(days=fs.alert_before_days if fs else 7)
    upcoming = (
        VaccinationSchedule.query
        .filter(
            VaccinationSchedule.barn_id == animal.barn_id,
            VaccinationSchedule.status == "scheduled",
            VaccinationSchedule.planned_date <= window_end,
        )
        .order_by(VaccinationSchedule.planned_date)
        .first()
    )
    if not upcoming:
        return None
    return {
        "message": f"فيه موعد تحصين مجدول لحظيرة {animal.barn.barn_name} بتاريخ {upcoming.planned_date} — تبي تراجع جدول التحصينات؟",
        "url_endpoint": "health.vaccination_schedule_list",
        "url_kwargs": {},
        "button_text": "افتح جدول التحصينات ←",
    }
