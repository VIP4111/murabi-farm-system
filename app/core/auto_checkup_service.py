"""فحوصات دورية تلقائية (بند إضافي، طلبك الصريح: "المفروض تجيله إشعار
تنبيه أو مهمة بشكل تلقائي... النظام يقوم بهذا الطلب... لأن الدكتور
ممكن يتكاسل أو يهمل النظام يجبره"). قبل هذا البند، "طلب فحص شامل"
كانت شاشة يدوية بس — النظام ما يبادر أبداً.

القاعدتان (بالضبط زي ما اتفقنا):
1. **رأس فيه مرض مفتوح** — يحتاج متابعة كل 3 أيام لين يُغلق المرض.
2. **رأس نشط ما له أي فحص مسجَّل من 30 يوم** — يحتاج فحص دوري.

كلتاهما تولّد مهام حقيقية عبر `task_service.create_suggested_task`
بـ`auto_approve=True` (نفس آلية `daily_task_service.py` بالضبط —
مهام النظام التلقائية، صفر انتظار اعتماد يدوي؛ "يجبره" بالضبط زي
طلبك) و`target_role="doctor"` — تصل لأي دكتور متاح فوراً بدون تدخل
صاحب الحلال."""
from datetime import date, timedelta

from app.extensions import db
from app.models import Animal, Disease, VetVisit, Task, CheckupItemPreset

DISEASE_FOLLOWUP_DAYS = 3
ROUTINE_CHECKUP_DAYS = 30

SOURCE_DISEASE = "AutoCheckupDisease"
SOURCE_ROUTINE = "AutoCheckupRoutine"


def _has_recent_auto_task(animal_id: int, source_type: str, since: date) -> bool:
    return db.session.query(Task.id).filter(
        Task.animal_id == animal_id, Task.source_type == source_type,
        Task.created_at >= since,
    ).first() is not None


def _last_checkup_date(animal_id: int) -> date | None:
    """آخر فحص حقيقي مسجَّل للرأس — إما زيارة بيطرية موثَّقة
    (`VetVisit`)، أو مهمة "فحص" (`animal_checkup`) أُنجزت فعلاً — أياً
    كان الأحدث."""
    last_visit = (db.session.query(db.func.max(VetVisit.date))
                  .filter(VetVisit.animal_id == animal_id).scalar())
    last_task_dt = (db.session.query(db.func.max(Task.completed_at))
                     .filter(Task.animal_id == animal_id, Task.task_type == "animal_checkup",
                             Task.status == "done").scalar())
    dates = [d for d in (last_visit, last_task_dt.date() if last_task_dt else None) if d]
    return max(dates) if dates else None


def _create_checkup_batch(*, animal: Animal, items: list[str], source_type: str, due_date: date) -> None:
    from app.team import task_service as tsvc
    source_id = None
    for item in items:
        task = tsvc.create_suggested_task(
            title=f"{item} — {animal.animal_no}", task_type="animal_checkup",
            animal_id=animal.id, barn_id=animal.barn_id, due_date=due_date,
            target_role="doctor", source_type=source_type, source_id=source_id,
            auto_approve=True,
        )
        if source_id is None:
            source_id = task.id
            task.source_id = source_id
            db.session.commit()


def generate_automatic_checkups(*, today: date) -> int:
    """تُستدعى يومياً (نفس دورة `daily_task_service.generate_daily_
    husbandry_tasks`) — تفحص كل رأس نشط وتولّد مهام فحص لو انطبقت أي
    قاعدة، بدون تكرار (حارس تعدّد المرات نفسه أدناه). ترجع عدد الرؤوس
    اللي تولّدت لها مهام جديدة هذا التشغيل."""
    items = CheckupItemPreset.active_texts()
    if not items:
        return 0
    generated = 0

    # القاعدة 1 — مرض مفتوح: كل 3 أيام لين يُغلق.
    diseased_animal_ids = {
        r[0] for r in db.session.query(Disease.animal_id)
        .join(Animal, Disease.animal_id == Animal.id)
        .filter(Disease.status == "active", Animal.status == "active").all()
    }
    cutoff_disease = today - timedelta(days=DISEASE_FOLLOWUP_DAYS)
    for animal_id in diseased_animal_ids:
        if _has_recent_auto_task(animal_id, SOURCE_DISEASE, cutoff_disease):
            continue
        animal = Animal.query.get(animal_id)
        _create_checkup_batch(animal=animal, items=items, source_type=SOURCE_DISEASE, due_date=today)
        generated += 1

    # القاعدة 2 — رأس نشط ما له فحص من 30 يوم (نتجاهل الرؤوس اللي
    # ولّدنا لها فحص مرض بنفس هالتشغيلة، عشان ما نكرر مهمتين بنفس اليوم).
    active_ids = {r[0] for r in db.session.query(Animal.id).filter(Animal.status == "active").all()}
    cutoff_routine = today - timedelta(days=ROUTINE_CHECKUP_DAYS)
    for animal_id in active_ids - diseased_animal_ids:
        last = _last_checkup_date(animal_id)
        if last and last > cutoff_routine:
            continue
        if _has_recent_auto_task(animal_id, SOURCE_ROUTINE, cutoff_routine):
            continue
        animal = Animal.query.get(animal_id)
        _create_checkup_batch(animal=animal, items=items, source_type=SOURCE_ROUTINE, due_date=today)
        generated += 1

    return generated
