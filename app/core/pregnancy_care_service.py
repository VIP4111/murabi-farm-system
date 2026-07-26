"""
رعاية الحمل المتأخر التلقائية (بند إضافي 51) — أول استخدام فعلي لحقل
`FarmSettings.pre_birth_feed_change_days` (كان موجوداً من قبل بدون أي
منطق يقرأه، انظر تدقيق بند 51). ما فيه مجدول/Cron بالمشروع — نفس فلسفة
`alerts_service.py` بالضبط: يُستدعى عند فتح شاشة التنبيهات، يفحص كل
حمل مؤكَّد، ويولّد مهمة مقترحة واحدة لكل حمل وصل مرحلته المتأخرة (مرة
وحدة بالضبط، بفحص idempotency عبر source_type/source_id=Pregnancy.id).
"""
from datetime import date, timedelta

from app.models import FarmSettings, Pregnancy, Task
from app.team import task_service


def generate_late_pregnancy_tasks() -> list[Task]:
    fs = FarmSettings.get()
    today = date.today()
    created = []

    for p in Pregnancy.query.filter_by(confirmed=True).all():
        if p.outcome:
            continue  # إجهاض مسجَّل — الحمل خرج من الدورة، لا داعي لمهمة تغذية
        animal = p.female
        if not animal or animal.status != "active":
            continue

        base_date = p.mating.date if p.mating else p.date
        expected_birth = base_date + timedelta(days=fs.gestation_days)
        trigger_date = expected_birth - timedelta(days=fs.pre_birth_feed_change_days)
        if today < trigger_date or today > expected_birth:
            continue

        existing = Task.query.filter_by(source_type="LatePregnancyCare", source_id=p.id).first()
        if existing:
            continue

        task = task_service.create_suggested_task(
            title=f"🤰 تعديل عليقة الثلث الأخير + تجريع وقائي — {animal.animal_no}",
            task_type="late_pregnancy_care",
            barn_id=animal.barn_id, animal_id=animal.id,
            due_date=today,
            source_type="LatePregnancyCare", source_id=p.id,
            notes=(
                f"الحمل بمرحلة متأخرة (تاريخ ولادة متوقع {expected_birth}) — "
                "تعديل العليقة إلى بروتين أعلى + تجريع وقائي "
                "(سيلينيوم + فيتامين E + AD3E)."
            ),
        )
        created.append(task)

    return created
