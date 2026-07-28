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

**إضافة (2026-07-23)**: كل تنبيه صار يحمل `barn_id` (حظيرة الحيوان
المرتبط، أو حظيرة البلاغ مباشرة لو ما له حيوان محدد) — أساس شاشة
"تنبيهاتي" للعامل المسؤول عن حظائر معيّنة (`core.alerts_mine`)، بدل ما
يحتاج صلاحية `animals.view` العامة لمجرد ما يشوف تنبيهات حظائره هو.
"""
from datetime import date, timedelta
from app.models import (
    Animal, Barn, Vaccination, ReproDevice, Disease, ProductionWorkflow, Report, FarmSettings,
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

    alerts = (
        _vaccinations_due(fs) + _withdrawal_ending_soon(fs) + _near_births()
        + _device_removal_due(fs) + _stale_open_diseases(fs) + _out_of_order_animals()
        + _stale_new_reports(fs) + _ready_to_sell_now() + _delayed_estrus(fs)
        + _barns_without_responsible_worker()
    )
    if barn_ids is not None:
        allowed = set(barn_ids)
        alerts = [a for a in alerts if a.get("barn_id") in allowed]
    alerts.sort(key=lambda a: not a["urgent"])
    return alerts
