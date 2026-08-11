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


class IsolationExitBlocked(Exception):
    """يُرفع لما تُحاول تخرج رأس من العزل قبل انتهاء المدة الأدنى بدون
    ما تجاوب على الأسئلة الإلزامية (فحص بيطري + تحصين)."""


def enter_isolation(*, animal_id: int, reason: str | None, note_date: date,
                     actor_user_id: int, barn_id: int | None = None) -> "Animal":
    """دخول عزل يدوي واضح (بند إضافي 148) — طلبك: "احتاج زر واضح عزل".
    لأي حالة استثنائية (اشتباه مرض، إصابة، إلخ) بمعزل عن خطة العزل
    التلقائية بعد الولادة. **idempotent على عداد الأيام**: لو الرأس
    أصلاً بالعزل (isolation_started_at مضبوط)، ما نصفّره — يستمر
    العد من أول دخول فعلي، حتى لو انتقل بين أكثر من حظيرة عزل."""
    from app.models import Animal, AuditLog, Barn

    animal = Animal.query.get(animal_id)
    if not animal:
        raise ValueError("الرأس غير موجود")

    target = Barn.query.get(barn_id) if barn_id else Barn.query.filter_by(barn_type="عزل").order_by(Barn.id).first()
    if not target:
        raise ValueError("ما فيه حظيرة عزل معرَّفة بالنظام")

    old_barn = animal.barn_id
    animal.barn_id = target.id
    if animal.isolation_started_at is None:
        animal.isolation_started_at = note_date
    db.session.add(animal)
    db.session.add(AuditLog(
        actor_user_id=actor_user_id, action="animal.enter_isolation",
        entity_type="Animal", entity_id=animal.id,
        details=f"barn {old_barn} -> {target.id} — {reason or ''}",
    ))
    if reason:
        from app.core.animal_service import add_note
        add_note(animal=animal, note_date=note_date, note=f"دخول عزل — {reason}", created_by_id=actor_user_id)
    db.session.commit()
    return animal


def exit_isolation(*, animal_id: int, target_barn_id: int, note_date: date, actor_user_id: int,
                    vet_checked: bool = False, vaccinated: bool = False, notes: str | None = None) -> "Animal":
    """خروج من العزل (بند إضافي 148) — طلبك: "لو طلعه قبل وقته يعطيني
    خيارات إلزامية مثل هل تم تحصينه". لو مرّت المدة الأدنى
    (`FarmSettings.isolation_days`) كامل، يخرج مباشرة بدون شرط. لو
    قبل وقتها، لازم تؤكد فحص بيطري + تحصين — وإلا تُرفض العملية بدل
    ما تُنجَز ناقصة صامتة."""
    from app.models import Animal, AuditLog, Barn, FarmSettings

    animal = Animal.query.get(animal_id)
    if not animal:
        raise ValueError("الرأس غير موجود")
    target = Barn.query.get(target_barn_id)
    if not target:
        raise ValueError("الحظيرة الهدف غير موجودة")

    settings = FarmSettings.get()
    days_in = (note_date - animal.isolation_started_at).days if animal.isolation_started_at else None
    is_early = days_in is not None and days_in < settings.isolation_days

    if is_early and not (vet_checked and vaccinated):
        missing = []
        if not vet_checked:
            missing.append("فحص بيطري موثّق")
        if not vaccinated:
            missing.append("تحصين")
        raise IsolationExitBlocked(
            f"خروج مبكر من العزل (باقي {settings.isolation_days - days_in} يوم من المدة الأدنى) — "
            f"يحتاج تأكيد: {'، '.join(missing)}."
        )

    old_barn = animal.barn_id
    animal.barn_id = target.id
    animal.isolation_started_at = None
    db.session.add(animal)
    db.session.add(AuditLog(
        actor_user_id=actor_user_id, action="animal.exit_isolation",
        entity_type="Animal", entity_id=animal.id,
        details=f"barn {old_barn} -> {target.id} — days_in={days_in} early={is_early}",
    ))
    note_text = f"خروج من العزل ({'مبكر' if is_early else 'بعد اكتمال المدة'})"
    if notes:
        note_text += f" — {notes}"
    from app.core.animal_service import add_note
    add_note(animal=animal, note_date=note_date, note=note_text, created_by_id=actor_user_id)
    db.session.commit()
    return animal


def start_isolation_plan(*, mother, newborn, birth_date_: date):
    """يُشغَّل تلقائياً عند تسجيل ولادة — يعزل الأم والمولود ويولّد مهام
    مقترحة (تحتاج موافقة الدكتور قبل ما توصل للعامل، حسب دورة حياة المهام)."""

    from app.models import Barn, FarmSettings
    settings = FarmSettings.get()

    isolation_barn = Barn.query.filter_by(barn_type="عزل").order_by(Barn.id).first()
    if isolation_barn:
        mother.barn_id = isolation_barn.id
        newborn.barn_id = isolation_barn.id
        mother.isolation_started_at = birth_date_
        newborn.isolation_started_at = birth_date_
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
        title=f"تجريع فيتامين هـ + سيلينيوم وقائي للمولود {newborn.animal_no}",
        task_type="selenium_dose", barn_id=barn_id, animal_id=newborn.id,
        due_date=birth_date_,
        notes="وقاية من مرض العضلة البيضاء (White Muscle Disease) — الجرعة الدقيقة حسب توصية الطبيب.",
        source_type="IsolationPlan", source_id=newborn.id,
    )
    task_service.create_suggested_task(
        title=f"تأكد رضاعة/لبأ المولود {newborn.animal_no} خلال {settings.colostrum_window_hours} ساعة",
        task_type="colostrum_check", barn_id=barn_id, animal_id=newborn.id,
        due_date=birth_date_,
        notes=f"السرسوب (اللبأ) خلال أول {settings.colostrum_window_hours} ساعة من الولادة ضروري لمناعة المولود المبكرة.",
        source_type="IsolationPlan", source_id=newborn.id,
    )
    task_service.create_suggested_task(
        title=f"جرعة معوية/تجشؤ وقائية للمولود {newborn.animal_no}",
        task_type="newborn_gut_dose", barn_id=barn_id, animal_id=newborn.id,
        due_date=birth_date_,
        notes="حسب توصية الطبيب — يشمل عادة مساعدة على التجشؤ وجرعة وقائية معوية أولى.",
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

    # بروتوكول الأم بعد الولادة (بند إضافي 188)
    task_service.create_suggested_task(
        title=f"تأكد نزول المشيمة كاملة — الأم {mother.animal_no} خلال {settings.placenta_check_hours} ساعة",
        task_type="placenta_check", barn_id=barn_id, animal_id=mother.id,
        due_date=birth_date_,
        notes="احتباس المشيمة أكثر من الفترة الطبيعية يحتاج تدخّل بيطري — لا تنتظر لو تجاوزت المدة.",
        source_type="IsolationPlan", source_id=mother.id,
    )
    task_service.create_suggested_task(
        title=f"مقوّيات وسوائل دافئة فور الولادة — الأم {mother.animal_no}",
        task_type="postpartum_tonic", barn_id=barn_id, animal_id=mother.id,
        due_date=birth_date_,
        notes="ماء دافئ + محلول مقوٍّ (حسب توصية الطبيب) يساعد تعافي الأم من إجهاد الولادة ويحفّز إدرار اللبأ.",
        source_type="IsolationPlan", source_id=mother.id,
    )
    for day_offset in range(1, settings.postpartum_mother_followup_days + 1):
        due = birth_date_ + timedelta(days=day_offset)
        task_service.create_suggested_task(
            title=f"متابعة نفاس يومية — الأم {mother.animal_no} (يوم {day_offset})",
            task_type="postpartum_mother_check", barn_id=barn_id, animal_id=mother.id,
            due_date=due,
            notes="راقب الشهية، الإفرازات، وسلامة الرضاعة — أي خمول أو إفراز كريه = استدعاء طبيب.",
            source_type="PostpartumMotherPlan", source_id=mother.id * 1000 + day_offset,
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
