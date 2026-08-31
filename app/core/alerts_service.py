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
16. (إضافي، بند 296) توقّع نفاد علف قريب — تحليل إحصائي لمعدل استهلاك
    الحركات الفعلية (FeedMovement) مقابل المخزون المتبقي (أول خطوة من
    خطة "عقل المزرعة" الاستباقية)

**إضافة (2026-07-23)**: كل تنبيه صار يحمل `barn_id` (حظيرة الحيوان
المرتبط، أو حظيرة البلاغ مباشرة لو ما له حيوان محدد) — أساس شاشة
"تنبيهاتي" للعامل المسؤول عن حظائر معيّنة (`core.alerts_mine`)، بدل ما
يحتاج صلاحية `animals.view` العامة لمجرد ما يشوف تنبيهات حظائره هو.
"""
import calendar
from datetime import date, datetime, timedelta
from flask_babel import gettext as _
from app.models import (
    Animal, Barn, Vaccination, ReproDevice, Disease, ProductionWorkflow, Report, FarmSettings, Pharmacy,
    AnimalWeight, Task, Feed, FeedMovement,
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
                "category": _("تحصين"), "icon": "💉",
                "label": _("%(no)s — %(vaccine)s", no=v.animal.animal_no, vaccine=v.vaccine_name),
                "detail": (_("متأخر منذ %(d)s", d=v.next_due_date) if overdue
                           else _("مستحق بتاريخ %(d)s", d=v.next_due_date)),
                "urgent": overdue, "animal_id": v.animal_id, "barn_id": v.animal.barn_id,
            })
    return alerts


def _withdrawal_ending_soon(fs: FarmSettings) -> list[dict]:
    """فترة سحب اللحم/الذبح — تنتهي البيع فقط. لفترة سحب الحليب انظر
    `_milk_withdrawal_ending_soon()` تحت (بند إضافي، 2026-08-30: طلبك
    الصريح إن التحريمين مستقلان)."""
    from app.health.health_service import animal_under_withdrawal
    today = date.today()
    window_end = today + timedelta(days=fs.alert_before_days)
    alerts = []
    for a in Animal.query.filter_by(status="active").all():
        until = animal_under_withdrawal(a.id)
        if until and until <= window_end:
            alerts.append({
                "category": _("فترة سحب"), "icon": "⏳",
                "label": _("%(no)s — تصير آمنة للبيع/الذبح بتاريخ %(d)s", no=a.animal_no, d=until),
                "detail": "", "urgent": False, "animal_id": a.id, "barn_id": a.barn_id,
            })
    return alerts


def _milk_withdrawal_ending_soon(fs: FarmSettings) -> list[dict]:
    """فترة سحب الحليب المستقلة (بند إضافي، 2026-08-30)."""
    from app.health.health_service import animal_under_milk_withdrawal
    today = date.today()
    window_end = today + timedelta(days=fs.alert_before_days)
    alerts = []
    for a in Animal.query.filter_by(status="active").all():
        until = animal_under_milk_withdrawal(a.id)
        if until and until <= window_end:
            alerts.append({
                "category": _("فترة سحب حليب"), "icon": "🥛",
                "label": _("%(no)s — يصير حليبها آمناً بتاريخ %(d)s", no=a.animal_no, d=until),
                "detail": "", "urgent": False, "animal_id": a.id, "barn_id": a.barn_id,
            })
    return alerts


def _near_births() -> list[dict]:
    from app.core.animal_filters_service import get_filtered
    return [
        {
            "category": _("ولادة متوقعة"), "icon": "🍼",
            "label": _("%(no)s — ولادة متوقعة قريباً", no=a.animal_no),
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
                "category": _("جهاز تكاثر"), "icon": "🔧",
                "label": _("%(no)s — إزالة %(device)s", no=(ewe.animal_no if ewe else '-'), device=d.device_type),
                "detail": (_("متأخر منذ %(d)s", d=d.planned_remove_at) if overdue
                           else _("موعد الإزالة %(d)s", d=d.planned_remove_at)),
                "urgent": overdue, "animal_id": ewe.id if ewe else None,
                "barn_id": ewe.barn_id if ewe else None,
            })
    return alerts


def _stale_open_diseases(fs: FarmSettings) -> list[dict]:
    cutoff = date.today() - timedelta(days=fs.alert_before_days)
    rows = Disease.query.filter(Disease.status == "active", Disease.date <= cutoff).all()
    return [
        {
            "category": _("مرض مفتوح"), "icon": "🌡️",
            "label": _("%(no)s — %(name)s", no=d.animal.animal_no, name=d.disease_name),
            "detail": _("مفتوح منذ %(d)s بدون إغلاق", d=d.date),
            "urgent": True, "animal_id": d.animal_id, "barn_id": d.animal.barn_id,
        }
        for d in rows
    ]


def _out_of_order_animals() -> list[dict]:
    rows = ProductionWorkflow.query.filter_by(status="out_of_order").all()
    return [
        {
            "category": _("ترتيب غير منتظم"), "icon": "⚠️",
            "label": _("%(no)s — دورة الإنتاج بترتيب غير منتظم", no=wf.animal.animal_no),
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
                "category": _("توقّف بدورة الإنتاج"), "icon": "⏸️",
                "label": _("%(no)s — واقف بمرحلة '%(stage)s' منذ %(days)s يوم",
                           no=wf.animal.animal_no, stage=wf.stage_name, days=days_stuck),
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
            "category": _("بلاغ منتظر"), "icon": "📋",
            "label": _("بلاغ #%(id)s من %(name)s — بانتظار الاستلام",
                       id=r.id, name=(r.reporter.name if r.reporter else '-')),
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
            "category": _("جاهز للبيع"), "icon": "💰",
            "label": _("%(no)s — %(label)s (درجة %(score)s)",
                       no=row['animal'].animal_no, label=row['label'], score=row['score']),
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
                "category": _("تأخر شياع"), "icon": "🔁",
                "label": _("%(no)s — تأخر حملها أكثر من %(days)s يوم", no=a.animal_no, days=fs.female_delayed_conception_days),
                "detail": _("بدون تقريع/حمل جديد منذ آخر ولادة أو تلقيح مسجَّل"),
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
                "category": _("بيانات ناقصة"), "icon": "📋",
                "label": _("%(no)s — ناقص: %(field)s", no=a.animal_no, field=dcs.FIELD_LABELS_AR[field]),
                "detail": _("أكمّل هذا الحقل من شاشة تعديل الحيوان."),
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
            "category": _("حظيرة بدون مسؤول"), "icon": "👷",
            "label": _("حظيرة %(no)s (%(name)s) — بدون عامل مسؤول", no=b.barn_no, name=b.display_name()),
            "detail": _("المهام والتنبيهات التلقائية لهذي الحظيرة ما توجّه لأحد لين تحدد مسؤولاً."),
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
        label = _("%(barn)s — %(pharmacy)s (بعد %(days)s يوم)",
                  barn=s.barn.display_name(), pharmacy=s.pharmacy.name, days=days_left)
        unit = s.pharmacy.unit or ""
        if s.pharmacy.default_dose_ml and head_count:
            needed = head_count * s.pharmacy.default_dose_ml
            available = s.pharmacy.available_qty or 0
            if needed > available:
                shortage = needed - available
                alerts.append({
                    "category": _("نقص مخزون تحصين مجدول"), "icon": "📦",
                    "label": label,
                    "detail": _("الاحتياج المتوقع %(needed).2f %(unit)s لـ%(head)s رأس، "
                                "والمتوفر %(available)g %(unit)s فقط — يوصى بشراء "
                                "%(shortage).2f %(unit)s إضافية على الأقل قبل الموعد.",
                                needed=needed, unit=unit, head=head_count, available=available, shortage=shortage),
                    "urgent": days_left <= 2, "animal_id": None, "barn_id": s.barn_id,
                })
            else:
                alerts.append({
                    "category": _("تذكير تحصين مجدول"), "icon": "📅",
                    "label": label,
                    "detail": _("المخزون كافٍ (%(available)g %(unit)s) لـ%(head)s رأس — جهّز الحظيرة بالموعد.",
                                available=available, unit=unit, head=head_count),
                    "urgent": False, "animal_id": None, "barn_id": s.barn_id,
                })
        else:
            alerts.append({
                "category": _("تذكير تحصين مجدول"), "icon": "📅",
                "label": label,
                "detail": _("%(head)s رأس بالحظيرة حالياً — سجّل جرعة افتراضية على الدواء لمقارنة المخزون تلقائياً.",
                            head=head_count),
                "urgent": False, "animal_id": None, "barn_id": s.barn_id,
            })
    return alerts


def _late_time_critical_tasks(fs: FarmSettings, *, now: datetime | None = None) -> list[dict]:
    """مهام لها موعد وقت محدد (`Task.due_time`، بند إضافي 278) —
    طلبك الصريح: "وضع العلف لو وصلت الساعة 8 معناتها متأخر، الساعة 9
    يعتبر إنذار يوصل لصاحب الحلال — حتى لو العامل أكد إنه أنجزها".
    `task_late_grace_minutes` (افتراضي ساعة) هو الفرق بين "الموعد" و
    "الإنذار الفعلي". يشمل حالتين: (1) لسا ما انجزت وفات الموعد+المهلة،
    (2) انجزت لكن بعد الموعد+المهلة — تقرير واقعة، مو منع أو حجب."""
    now = now or datetime.now()
    today = now.date()
    grace = timedelta(minutes=fs.task_late_grace_minutes)
    tasks = Task.query.filter(
        Task.due_date == today, Task.due_time.isnot(None),
        Task.status.notin_(["cancelled", "deleted_pending_review", "postponed"]),
    ).all()
    alerts = []
    for t in tasks:
        deadline = datetime.combine(today, t.due_time) + grace
        if t.status == "done":
            if t.completed_at and t.completed_at > deadline:
                who = t.accepted_by.name if t.accepted_by else (t.assignee.name if t.assignee else _("غير محدد"))
                alerts.append({
                    "category": _("مهمة أُنجزت متأخرة عن موعدها"), "icon": "🕘",
                    "label": _("%(title)s — أُنجزت الساعة %(time)s", title=t.title, time=t.completed_at.strftime('%H:%M')),
                    "detail": _("موعدها كان %(due)s — نفّذها: %(who)s.", due=t.due_time.strftime('%H:%M'), who=who),
                    "urgent": False, "animal_id": None, "barn_id": t.barn_id,
                    "task_id": t.id,
                })
        elif now > deadline:
            who = t.assignee.name if t.assignee else _("بدون عامل مكلَّف")
            alerts.append({
                "category": _("مهمة متأخرة عن موعدها"), "icon": "⏰",
                "label": _("%(title)s — لسا ما انجزت", title=t.title),
                "detail": _("موعدها كان %(due)s — العامل المكلَّف: %(who)s.", due=t.due_time.strftime('%H:%M'), who=who),
                "urgent": True, "animal_id": None, "barn_id": t.barn_id,
                "task_id": t.id,
            })
    return alerts


def _equipment_needs_maintenance() -> list[dict]:
    """معدة تحتاج صيانة (بند إضافي 276) — طلبك الصريح: "ضيف تنبيه في
    حال نحتاج صيانة لصاحب الحلال". يُرفع تلقائياً من `Equipment.needs_maintenance`
    (تسجّله شاشة الحركة/الاستلام لما يُختار "تحتاج صيانة" وقت التسليم أو
    الاستلام)، وينزل يدوياً من شاشة تعديل الصنف بعد الإصلاح الفعلي."""
    from app.extensions import db
    from app.models import Equipment, EquipmentMovement
    items = Equipment.query.filter_by(needs_maintenance=True).all()
    alerts = []
    for item in items:
        last = (EquipmentMovement.query.filter_by(equipment_id=item.id)
                .filter(db.or_(EquipmentMovement.condition_at_handout == "needs_maintenance",
                                EquipmentMovement.condition_at_return == "needs_maintenance"))
                .order_by(EquipmentMovement.created_at.desc()).first())
        who = None
        if last:
            who = last.borrowed_by.name if last.borrowed_by else None
        detail = _("آخر من استعملها: %(who)s", who=who) if who else _("راجع شاشة حركة الصنف لمعرفة آخر من استعملها.")
        alerts.append({
            "category": _("معدة تحتاج صيانة"), "icon": "🔧",
            "label": _("%(name)s — تحتاج صيانة", name=item.name),
            "detail": detail,
            "urgent": False, "animal_id": None, "barn_id": None,
            "equipment_id": item.id,
        })
    return alerts


def _month_range(start_year: int, start_month: int, end_year: int, end_month: int) -> list[tuple[int, int]]:
    """كل الأشهر (سنة، شهر) من البداية للنهاية شاملة الطرفين، بالترتيب."""
    months = []
    y, m = start_year, start_month
    while (y, m) <= (end_year, end_month):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def _payroll_month_end_reminder() -> list[dict]:
    """تذكير رواتب آخر كل شهر (بند إضافي 246، طلبك الصريح: "احتاج
    تنبيه برواتب كل اخر شهر مع تأكيد لو فيه خصومات على العامل") — نفس
    فلسفة هذا الملف بالضبط (فحص حي عند فتح شاشة التنبيهات، بدون Cron).

    يغطي حالتين:
    1. الشهر الحالي، بس خلال آخر `PAYROLL_MONTH_END_REMINDER_DAYS` أيام
       منه — تذكير عادي، ما فيه داعي يزعج قبل قرب نهاية الشهر.
    2. **أي شهر سابق كامل** (من أول شهر تأسَّس فيه نظام الرواتب فعلياً —
       أقدم سجل `Payroll` بالنظام كله — لين الشهر قبل الحالي) ما تأكَّد
       راتب العامل فيه. هذي الحالة أُضيفت لاحقاً (نفس البند) بعد ملاحظة
       صريحة منك: التذكير الأصلي كان يشتغل بس آخر 3 أيام من الشهر
       الحالي، فلو صاحب الحلال فاته الشهر كامل بدون ما يفتح التطبيق،
       ما فيه أي شي يذكّره بعدها — صارت الآن حالة "متأخر" دائمة تبقى
       تظهر لين يتحل، بغض النظر أي يوم احنا فيه الحين.
    """
    from app.models import Payroll, User
    today = date.today()
    days_in_month = calendar.monthrange(today.year, today.month)[1]

    earliest = Payroll.query.order_by(Payroll.year, Payroll.month).first()
    if earliest is None:
        # ما فيه أي راتب اتسجَّل بالنظام كله بعد — ما فيه أساس نحكم
        # منه على "شهر متأخر"، فقط الشهر الحالي (لو قرب ينتهي) يُفحص.
        past_months = []
    else:
        prev_year, prev_month = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
        past_months = _month_range(earliest.year, earliest.month, prev_year, prev_month)

    is_near_current_month_end = today.day >= days_in_month - PAYROLL_MONTH_END_REMINDER_DAYS + 1
    months_to_check = list(past_months)
    if is_near_current_month_end:
        months_to_check.append((today.year, today.month))

    if not months_to_check:
        return []

    alerts = []
    workers = User.query.filter(User.is_active_account == True, User.base_salary.isnot(None)).all()  # noqa: E712
    for w in workers:
        # ما نطالب عامل براتب شهر قبل ما أصلاً كان له حساب بالنظام —
        # `created_at` تاريخ إنشاء حسابه.
        joined = w.created_at.date() if w.created_at else date.min
        for (y, m) in months_to_check:
            if (y, m) < (joined.year, joined.month):
                continue
            payroll = Payroll.query.filter_by(user_id=w.id, year=y, month=m).first()
            if payroll and payroll.status == "confirmed":
                continue
            is_current_month = (y, m) == (today.year, today.month)
            if payroll and payroll.total_deductions > 0:
                detail = _("فيه مسودة راتب محفوظة عليها خصومات بقيمة %(amount).2f — راجعها قبل التأكيد.",
                           amount=payroll.total_deductions)
            elif is_current_month:
                detail = _("لسا ما تجهَّز راتب هذا الشهر له.")
            else:
                detail = _("راتب شهر سابق ما تأكَّد بعد — متأخر، راجعه بأقرب فرصة.")
            alerts.append({
                "category": _("تذكير رواتب نهاية الشهر"), "icon": "💰",
                "label": _("راتب %(name)s — %(m)s/%(y)s", name=w.name, m=m, y=y),
                "detail": detail,
                "urgent": (is_current_month and today.day == days_in_month) or not is_current_month,
                "animal_id": None, "barn_id": None,
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
            "category": _("قرب انتهاء صلاحية دواء"), "icon": "⏳",
            "label": _("%(name)s — %(qty)g %(unit)s", name=p.name, qty=(p.available_qty or 0), unit=(p.unit or '')),
            "detail": (_("منتهي الصلاحية منذ %(d)s", d=today - expiry) if expired
                       else _("تنتهي صلاحيته بتاريخ %(d)s", d=expiry)),
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
            "category": _("حظيرة هدف ناقصة"), "icon": "🏚️",
            "label": _("%(n)s رأس بحاجة حظيرة \"%(type)s\" — ما أنشأتها بعد", n=len(animal_ids), type=target_barn_type),
            "detail": _("أنشئ حظيرة بنوع \"%(type)s\" من شاشة الحظائر، عشان النظام "
                        "يقدر يقترح نقل هالرؤوس تلقائياً (بانتظار موافقة الدكتور دائماً).", type=target_barn_type),
            "urgent": False, "animal_id": None, "barn_id": None,
        })

    open_pregnant_move_tasks = Task.query.filter(
        Task.task_type == "move_to_pregnant_barn",
        Task.status.in_(("suggested", "pending", "in_progress")),
    ).count()
    if open_pregnant_move_tasks and not Barn.query.filter_by(barn_type="حوامل").first():
        alerts.append({
            "category": _("حظيرة هدف ناقصة"), "icon": "🏚️",
            "label": _("%(n)s مهمة \"نقل لحظيرة الحوامل\" بانتظار حظيرة \"حوامل\" غير موجودة", n=open_pregnant_move_tasks),
            "detail": _("أنشئ حظيرة بنوع \"حوامل\" من شاشة الحظائر — بدونها المهمة ما تقدر تنقل الرأس فعلياً "
                        "لما تُنجَز (تقدر تختار حظيرة بديلة يدوياً وقت الإنجاز لو ما تبي تنشئ هذا النوع)."),
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
        "category": _("بيانات ناقصة"), "icon": "⚖️",
        "label": _("%(n)s رأس ما راح يدخل جدولة الأوزان المتأخرة إطلاقاً", n=len(missing)),
        "detail": _("ما عندها وزن مسجَّل ولا تاريخ ولادة/شراء/دخول — بدون أي تاريخ مرجعي، "
                    "النظام ما يقدر يحسب \"من متى ما اتوزنت\"، فتنبيه الوزن المتأخر ما يشتغل "
                    "لها أبداً. أكمّل تاريخ الشراء/الدخول أو سجّل وزناً أول من شاشة تعديل الحيوان."),
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
            "category": _("عزل بدون حظيرة مصنّفة"), "icon": "🚧",
            "label": _("%(n)s رأس بمهام عزل بدون حظيرة عزل فعلية", n=len(animal_ids)),
            "detail": _("ما فيه حظيرة بنوع \"عزل\" بالنظام — الأم والمولود ما انتقلوا فعلياً "
                        "لحظيرة عزل منفصلة عن باقي القطيع. أنشئ حظيرة جديدة بنوع \"عزل\" من "
                        "شاشة الحظائر عشان العزل التلقائي يشتغل صح للولادات الجاية."),
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
            "category": _("عزل بدون حظيرة مصنّفة"), "icon": "🚧",
            "label": _("%(n)s رأس أجهض بدون عزل فعلي — ما فيه حظيرة عزل", n=len(animal_ids2)),
            "detail": _("ما فيه حظيرة بنوع \"عزل\" بالنظام — الرأس المُجهِض ما انتقل لعزل طبي "
                        "منفصل ولسا يخالط باقي القطيع رغم احتمال عدوى. أنشئ حظيرة بنوع \"عزل\" "
                        "من شاشة الحظائر ثم انقل الرأس يدوياً."),
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
            "category": _("توزيع علف ناقص"), "icon": "🥣",
            "label": _("%(title)s — العلف ما اتوزّع بالكامل", title=t.title),
            "detail": (t.completion_note or "").strip(),
            "urgent": True, "animal_id": t.animal_id, "barn_id": t.barn_id,
        }
        for t in rows
    ]


FEED_DEPLETION_WINDOW_DAYS = 14
FEED_DEPLETION_MIN_MOVEMENTS = 3
FEED_DEPLETION_ALERT_DAYS = 5


def _feed_depletion_forecast() -> list[dict]:
    """توقّع نفاد علف قريب (بند إضافي 296 — المرحلة ١ من خطة "عقل
    المزرعة") — أول خطوة فعلية بخطة الوكيل الاستباقي: تحليل إحصائي
    بسيط بدون أي نموذج لغوي، بنفس فلسفة هذا الملف بالضبط (حساب حي عند
    فتح الشاشة، بدون Cron). الفكرة: معدل الاستهلاك الفعلي الحقيقي
    موجود أصلاً بـ`FeedMovement` (كل خصم توزيع علف تلقائي، بند 134،
    يسجّل حركة `out` هناك) — بدون أي حقل أو جدول جديد نحسب متوسط
    الاستهلاك اليومي لكل صنف علف آخر `FEED_DEPLETION_WINDOW_DAYS` يوم،
    ونقارنه بالمخزون المتبقي فعلياً (`Feed.available_qty`) لنتوقّع
    بعد كم يوم ينفد الصنف لو استمر نفس المعدل.

    **نطاق متعمَّد**: صنف عنده أقل من `FEED_DEPLETION_MIN_MOVEMENTS`
    حركة صادرة بالنافذة يُتجاهَل (بيانات غير كافية لمعدل موثوق — نفس
    منطق `WEIGHT_TREND_MIN_COHORT` ببند 97). التنبيه يظهر بس لو الأيام
    المتبقية المتوقَّعة ≤ `FEED_DEPLETION_ALERT_DAYS`، ويُعتبر عاجلاً
    دائماً لو المخزون نفد فعلياً (صفر أو أقل) أو الأيام المتبقية ≤ يومين."""
    window_start = datetime.now() - timedelta(days=FEED_DEPLETION_WINDOW_DAYS)
    rows = (FeedMovement.query
            .filter(FeedMovement.movement_type == "out", FeedMovement.created_at >= window_start)
            .all())

    out_by_feed: dict[int, list[FeedMovement]] = {}
    for m in rows:
        out_by_feed.setdefault(m.feed_id, []).append(m)

    alerts = []
    for feed_id, movements in out_by_feed.items():
        if len(movements) < FEED_DEPLETION_MIN_MOVEMENTS:
            continue
        feed = movements[0].feed
        if feed is None:
            continue
        total_out = sum(m.quantity or 0 for m in movements)
        span_days = max((datetime.now() - min(m.created_at for m in movements)).days, 1)
        daily_rate = total_out / span_days
        if daily_rate <= 0:
            continue
        available = feed.available_qty or 0
        days_remaining = available / daily_rate
        if days_remaining > FEED_DEPLETION_ALERT_DAYS:
            continue
        urgent = available <= 0 or days_remaining <= 2
        alerts.append({
            "category": _("توقّع نفاد علف"), "icon": "⏳",
            "label": _("%(name)s — يتوقّع نفاده خلال %(days).1f يوم", name=feed.name, days=days_remaining),
            "detail": _("المتبقي %(available).1f %(unit)s، بمعدل استهلاك "
                        "%(rate).1f %(unit)s/يوم آخر %(span)s يوم — يوصى بطلب شراء الآن.",
                        available=available, unit=(feed.unit or 'كجم'), rate=daily_rate, span=span_days),
            "urgent": urgent, "animal_id": None, "barn_id": None,
        })
    return alerts


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
            "category": _("مهمة متعذّرة بانتظار المراجعة"), "icon": "🚫",
            "label": _("%(title)s — %(reason)s", title=t.title, reason=(t.failure_reason or _("سبب غير محدد"))),
            "detail": (t.completion_note or "").strip() or _("بدون ملاحظة إضافية من العامل."),
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
            "category": _("مهمة مقترحة بانتظار الاعتماد"), "icon": "📥",
            "label": _("%(title)s — بانتظار اعتمادك من قبل %(d)s", title=t.title, d=t.created_at.date()),
            "detail": _("افتح شاشة \"مهام مقترحة بانتظار الاعتماد\" واعتمدها أو أجّلها أو احذفها."),
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
                "category": _("تباطؤ نمو مشبوه"), "icon": "📉",
                "label": _("%(no)s — معدل نموه %(rate).2f كجم/يوم", no=animal.animal_no, rate=rate),
                "detail": (_("ينقص وزنه فعلياً (متوسط حظيرته %(avg).2f كجم/يوم) — يوصى بفحص صحي عاجل", avg=barn_avg)
                           if losing_weight else
                           _("أبطأ بوضوح من متوسط حظيرته (%(avg).2f كجم/يوم) — يوصى بفحص صحي", avg=barn_avg)),
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


def get_alerts(barn_ids: list[int] | None = None, *, now: datetime | None = None) -> list[dict]:
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
        _vaccinations_due(fs) + _withdrawal_ending_soon(fs) + _milk_withdrawal_ending_soon(fs) + _near_births()
        + _device_removal_due(fs) + _stale_open_diseases(fs) + _out_of_order_animals()
        + _stale_new_reports(fs) + _ready_to_sell_now() + _delayed_estrus(fs)
        + _barns_without_responsible_worker() + _upcoming_vaccination_stock_shortage(fs)
        + _medicine_expiring_soon(fs) + _weight_gain_underperformers()
        + _failed_tasks_pending_review() + _isolation_without_barn()
        + _incomplete_animal_data() + _stalled_workflow(fs)
        + _barn_physiology_target_missing() + _weight_schedule_missing_reference_date()
        + _feed_distribution_shortage() + _suggested_tasks_pending_approval()
        + _payroll_month_end_reminder() + _equipment_needs_maintenance()
        + _late_time_critical_tasks(fs, now=now) + _feed_depletion_forecast()
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
    "توقّع نفاد علف": lambda aid: ("feed.purchase_new", {}),
}


def alert_action_url(alert: dict) -> str | None:
    """رابط "حل هذي المشكلة" لتنبيه واحد — يستخدم `_ALERT_ACTION_ROUTES`
    أعلاه. يرجّع None لو الفئة ما عندها إجراء مباشر (تبقى معلوماتية)."""
    from flask import url_for
    if alert.get("category") == "معدة تحتاج صيانة" and alert.get("equipment_id"):
        return url_for("equipment.items_edit", item_id=alert["equipment_id"])
    if alert.get("category") in ("مهمة متأخرة عن موعدها", "مهمة أُنجزت متأخرة عن موعدها") and alert.get("task_id"):
        return url_for("team.task_detail", task_id=alert["task_id"])
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
        "message": _("فيه موعد تحصين مجدول لحظيرة %(barn)s بتاريخ %(date)s — تبي تراجع جدول التحصينات؟",
                      barn=animal.barn.display_name(), date=upcoming.planned_date),
        "url_endpoint": "health.vaccination_schedule_list",
        "url_kwargs": {},
        "button_text": _("افتح جدول التحصينات ←"),
    }
