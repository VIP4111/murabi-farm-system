"""
خطة العزل التلقائية بعد الولادة (المرحلة 4). تُستدعى تلقائياً من
app/core/animal_service.create_animal() عند تسجيل مولود جديد — نقطة دخول
واحدة، بدون زر يدوي منفصل.

كل الأرقام الزمنية هنا تُقرأ من `FarmSettings` (قابلة للتعديل من شاشة
الإعدادات بدون أي تعديل كود) — مو ثابتة بالكود.
"""
from datetime import date, timedelta
from app.extensions import db
from app.team import task_service


def start_isolation_plan(*, mother, newborn, birth_date_: date):
    """يُشغَّل تلقائياً عند تسجيل ولادة — يعزل الأم والمولود ويولّد مهام
    مقترحة (تحتاج موافقة الدكتور قبل ما توصل للعامل، حسب دورة حياة المهام)."""

    from app.models import Barn, FarmSettings
    settings = FarmSettings.get()

    isolation_barn = Barn.query.filter_by(barn_type="عزل").order_by(Barn.id).first()
    if isolation_barn:
        mother.barn_id = isolation_barn.id
        newborn.barn_id = isolation_barn.id
        db.session.add(mother)
        db.session.add(newborn)
        db.session.commit()

    barn_id = isolation_barn.id if isolation_barn else None

    for day_offset in range(1, settings.isolation_days + 1):
        due = birth_date_ + timedelta(days=day_offset)
        task_service.create_suggested_task(
            title=f"فحص عزل يومي — الأم {mother.animal_no} والمولود {newborn.animal_no} (يوم {day_offset})",
            task_type="isolation_check", barn_id=barn_id, animal_id=newborn.id,
            due_date=due, source_type="IsolationPlan", source_id=newborn.id,
        )

    task_service.create_suggested_task(
        title=f"فحص دكتور إلزامي خلال {settings.doctor_check_hours} ساعة — الأم {mother.animal_no} والمولود {newborn.animal_no}",
        task_type="doctor_review", barn_id=barn_id, animal_id=newborn.id,
        due_date=birth_date_ + timedelta(hours=settings.doctor_check_hours),
        source_type="IsolationPlan", source_id=newborn.id,
    )

    # رعاية أولية للمولود (بند إضافي 51) — ثلاث مهام فورية (نفس يوم
    # الولادة) كانت غائبة كلياً: تعقيم السرة كان مجرد خانة تأكيد يدوية
    # على BirthRecord بدون أي مهمة تُذكِّر فيها، ونفس القيد بالضبط
    # لتأكد الرضاعة/اللبأ.
    task_service.create_suggested_task(
        title=f"تعقيم سرة المولود {newborn.animal_no}",
        task_type="cord_antisepsis", barn_id=barn_id, animal_id=newborn.id,
        due_date=birth_date_,
        source_type="IsolationPlan", source_id=newborn.id,
    )
    task_service.create_suggested_task(
        title=f"تجريع سيلينيوم للمولود {newborn.animal_no}",
        task_type="selenium_dose", barn_id=barn_id, animal_id=newborn.id,
        due_date=birth_date_,
        source_type="IsolationPlan", source_id=newborn.id,
    )
    task_service.create_suggested_task(
        title=f"تأكد رضاعة/لبأ المولود {newborn.animal_no}",
        task_type="colostrum_check", barn_id=barn_id, animal_id=newborn.id,
        due_date=birth_date_,
        source_type="IsolationPlan", source_id=newborn.id,
    )

    task_service.create_suggested_task(
        title=f"وزن المولود {newborn.animal_no}",
        task_type="weighing", barn_id=barn_id, animal_id=newborn.id,
        due_date=birth_date_ + timedelta(days=settings.isolation_days),
        requires_photo=False,
        source_type="IsolationPlan", source_id=newborn.id,
    )

    task_service.create_suggested_task(
        title=f"تحصين الأم {mother.animal_no} بعد الولادة",
        task_type="vaccination_due", barn_id=barn_id, animal_id=mother.id,
        due_date=birth_date_ + timedelta(days=settings.postpartum_vaccination_days),
        source_type="IsolationPlan", source_id=mother.id,
    )
    task_service.create_suggested_task(
        title=f"تحصين المولود {newborn.animal_no}",
        task_type="vaccination_due", barn_id=barn_id, animal_id=newborn.id,
        due_date=birth_date_ + timedelta(days=settings.postpartum_vaccination_days),
        source_type="IsolationPlan", source_id=newborn.id,
    )

    task_service.create_suggested_task(
        title=f"تبديل علف الأم {mother.animal_no} لوصفة النفاس",
        task_type="feed_switch", barn_id=barn_id, animal_id=mother.id,
        due_date=birth_date_,
        source_type="IsolationPlan", source_id=mother.id,
        notes=f"يبقى على علف النفاس {settings.postpartum_feed_days} يوم بعد الولادة حسب الإعدادات.",
    )


def record_abortion(*, pregnancy, outcome_date, notes: str | None, actor_user_id: int) -> dict:
    """بروتوكول الإجهاض والعزل الطبي (بند إضافي 51) — عند تسجيل إجهاض:
    (أ) نقل فوري لحظيرة العزل الطبي، (ب) مهمة سحب عيّنات (بروسيلا/
    كلاميديا/توكسوبلازما)، (ج) مهمة مراقبة حرارة واحدة لكل رأس ثاني
    كان بنفس حظيرة الأم وقت الإجهاض (لا يومية × N — عدد مهام واقعي)،
    بموعد استحقاق نهاية نافذة `abortion_barn_monitor_days`."""
    from datetime import timedelta
    from app.models import Animal, AuditLog, Barn, FarmSettings

    settings = FarmSettings.get()
    animal = pregnancy.female
    original_barn_id = animal.barn_id

    pregnancy.outcome = "abortion"
    pregnancy.outcome_date = outcome_date
    pregnancy.outcome_notes = notes
    db.session.add(pregnancy)

    isolation_barn = Barn.query.filter_by(barn_type="عزل").order_by(Barn.id).first()
    if isolation_barn:
        animal.barn_id = isolation_barn.id
        db.session.add(animal)

    db.session.add(AuditLog(
        actor_user_id=actor_user_id, action="pregnancy.abortion",
        entity_type="Pregnancy", entity_id=pregnancy.id, details=notes or "",
    ))
    db.session.commit()

    task_barn_id = isolation_barn.id if isolation_barn else animal.barn_id

    sampling_task = task_service.create_suggested_task(
        title=f"🧪 سحب عيّنات إجهاض — {animal.animal_no} (بروسيلا/كلاميديا/توكسوبلازما)",
        task_type="abortion_sampling", barn_id=task_barn_id, animal_id=animal.id,
        due_date=outcome_date,
        source_type="AbortionEvent", source_id=pregnancy.id,
        notes="سحب عيّنات مخبرية للفحص التفريقي — بروسيلا/كلاميديا/توكسوبلازما.",
    )

    monitor_tasks = []
    if original_barn_id:
        monitor_until = outcome_date + timedelta(days=settings.abortion_barn_monitor_days)
        barnmates = (Animal.query.filter_by(barn_id=original_barn_id, status="active")
                     .filter(Animal.id != animal.id).all())
        for mate in barnmates:
            monitor_tasks.append(task_service.create_suggested_task(
                title=f"🌡️ مراقبة حرارة (اشتباه إجهاض بالحظيرة) — {mate.animal_no}",
                task_type="abortion_barn_monitor", barn_id=original_barn_id, animal_id=mate.id,
                due_date=monitor_until,
                source_type="AbortionEvent", source_id=pregnancy.id,
                notes=(
                    f"راقب درجة حرارة هذا الرأس يومياً حتى {monitor_until} — "
                    "احتمال انتشار سبب معدٍ للإجهاض بنفس الحظيرة."
                ),
            ))

    return {
        "animal": animal, "isolated": bool(isolation_barn),
        "sampling_task": sampling_task, "monitor_tasks": monitor_tasks,
    }
