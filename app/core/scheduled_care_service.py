"""مهام ذكية من مصادر ثانية غير العزل (بند إضافي 149) — كان "المهام
الذكية" لا تتولّد تلقائياً إلا من خطة العزل بعد الولادة (راجع ROADMAP.md
بند 6: "ناقص: توليد مهام ذكية من مصادر ثانية غير العزل — تطعيمات مستحقة
عامة، أوزان متأخرة..."). هذا الملف يسدّ هذين المصدرين بنفس الفلسفة
الموجودة أصلاً بكل الملفات المشابهة (`feeding_schedule_service`,
`barn_physiology_service`, `data_completeness_service`): فحص حي عند فتح
شاشة التنبيهات، بدون Cron، idempotent عبر `source_type`/`source_id`."""
import zlib
from datetime import date, datetime

from app.models import Animal, Task, Vaccination
from app.models.animal_log import AnimalWeight
from app.team import task_service

VACCINATION_SOURCE_TYPE = "GeneralVaccinationDue"
WEIGHT_SOURCE_TYPE = "OverdueWeightCheck"


def _source_id(prefix: str, animal_id: int) -> int:
    return zlib.crc32(f"{prefix}:{animal_id}".encode()) & 0x7FFFFFFF


def generate_vaccination_due_tasks(*, now: datetime | None = None) -> list:
    """تطعيمات مستحقة عامة — نفس تعريف "مستحق" المستخدم أصلاً بتنبيه
    `alerts_service._vaccinations_due` (آخر `Vaccination.next_due_date`
    لكل رأس نشط <= اليوم)، بس هنا نولّد مهمة فعلية موجَّهة لعامل/دكتور
    الحظيرة بدل ما تبقى مجرد تنبيه سلبي — مو مرتبطة بمسار العزل بعد
    الولادة إطلاقاً."""
    today = (now or datetime.now()).date()
    created = []

    rows = Vaccination.query.filter(Vaccination.next_due_date.isnot(None)).all()
    latest_by_animal = {}
    for v in rows:
        prev = latest_by_animal.get(v.animal_id)
        if prev is None or v.date > prev.date:
            latest_by_animal[v.animal_id] = v

    for v in latest_by_animal.values():
        animal = v.animal
        if animal is None or animal.status != "active":
            continue
        if v.next_due_date > today:
            continue
        source_id = _source_id("vacc", animal.id)
        existing = Task.query.filter(
            Task.source_type == VACCINATION_SOURCE_TYPE, Task.source_id == source_id,
            Task.status.in_(task_service.OPEN_TASK_STATUSES),
        ).first()
        if existing:
            continue
        overdue_days = (today - v.next_due_date).days
        task = task_service.create_suggested_task(
            title=f"💉 تحصين مستحق — {animal.animal_no} ({v.vaccine_name})",
            task_type="vaccination_due",
            animal_id=animal.id, barn_id=animal.barn_id,
            due_date=today, source_type=VACCINATION_SOURCE_TYPE, source_id=source_id,
            notes=f"آخر تحصين مسجَّل استحق تجديده منذ {overdue_days} يوم (يوم الاستحقاق {v.next_due_date}).",
        )
        created.append(task)

    if created:
        from app.core.scheduled_care_notify_service import notify_new_care_tasks
        notify_new_care_tasks(created)

    return created


def generate_overdue_weight_tasks(*, now: datetime | None = None) -> list:
    """أوزان متأخرة — أي رأس نشط (مجترات فقط، النعام له وحدات وزن
    مختلفة) ما اتوزن من فترة أطول من `FarmSettings.weight_check_interval_days`
    (أو ما اتوزن إطلاقاً)، يولّد مهمة "متابعة إعادة وزن" — نفس `task_type`
    الموجود أصلاً (`reweigh_followup`) بس من مصدر دوري عام بدل ما يكون
    بس رد فعل بعد علاج معيّن."""
    from app.models import FarmSettings

    settings = FarmSettings.get()
    today = (now or datetime.now()).date()
    created = []

    animals = Animal.query.filter_by(status="active", species="sheep_goat").all()
    for animal in animals:
        last_weight = (AnimalWeight.query.filter_by(animal_id=animal.id)
                       .order_by(AnimalWeight.date.desc()).first())
        reference_date = last_weight.date if last_weight else (animal.birth_date or animal.purchase_date or animal.entry_date)
        if reference_date is None:
            continue
        days_since = (today - reference_date).days
        if days_since < settings.weight_check_interval_days:
            continue

        source_id = _source_id("weight", animal.id)
        existing = Task.query.filter(
            Task.source_type == WEIGHT_SOURCE_TYPE, Task.source_id == source_id,
            Task.status.in_(task_service.OPEN_TASK_STATUSES),
        ).first()
        if existing:
            continue
        task = task_service.create_suggested_task(
            title=f"⚖️ وزن متأخر — {animal.animal_no} (آخر وزن منذ {days_since} يوم)",
            task_type="reweigh_followup",
            animal_id=animal.id, barn_id=animal.barn_id,
            due_date=today, source_type=WEIGHT_SOURCE_TYPE, source_id=source_id,
            notes=f"آخر وزن مسجَّل بتاريخ {reference_date or '-'} — تجاوز فترة المتابعة الدورية ({settings.weight_check_interval_days} يوم).",
        )
        created.append(task)

    if created:
        from app.core.scheduled_care_notify_service import notify_new_care_tasks
        notify_new_care_tasks(created)

    return created
