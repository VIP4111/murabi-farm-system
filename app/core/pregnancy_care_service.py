"""
رعاية الحمل المتأخر التلقائية (بند إضافي 51) — أول استخدام فعلي لحقل
`FarmSettings.pre_birth_feed_change_days` (كان موجوداً من قبل بدون أي
منطق يقرأه، انظر تدقيق بند 51). ما فيه مجدول/Cron بالمشروع — نفس فلسفة
`alerts_service.py` بالضبط: يُستدعى عند فتح شاشة التنبيهات، يفحص كل
حمل مؤكَّد، ويولّد مهمة مقترحة واحدة لكل حمل وصل مرحلته المتأخرة (مرة
وحدة بالضبط، بفحص idempotency عبر source_type/source_id=Pregnancy.id).
"""
from datetime import date, timedelta

from app.extensions import db
from app.models import Animal, FarmSettings, Mating, Pregnancy, Task
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


def detect_implicit_pregnancies() -> list[Pregnancy]:
    """كشف حمل ضمني (بند إضافي 236) — نفس فلسفة `generate_late_pregnancy_
    tasks` أعلاه بالضبط (تُستدعى عند فتح شاشة التنبيهات، idempotency عبر
    source_type/source_id). لو تقريع مسجَّل مرّ عليه `estrus_return_window_
    days` بدون ما ترجع الأنثى للفحل مرة ثانية خلال نفس النافذة، هذا مؤشر
    حمل قوي (مو تأكيد طبي) — نسجّل حمل غير مؤكَّد مربوط بالتقريع نفسه
    (`mating_id`)، ونجدول فحص سونار تلقائياً بدل ما يبقى بانتظار تسجيل
    يدوي قد يُنسى تماماً."""
    fs = FarmSettings.get()
    today = date.today()
    created = []

    cutoff = today - timedelta(days=fs.estrus_return_window_days)
    for mating in Mating.query.filter(Mating.date <= cutoff).all():
        female = mating.female
        if not female or female.status != "active":
            continue

        if Pregnancy.query.filter_by(mating_id=mating.id).first():
            continue  # هذا التقريع بالذات أصلاً له سجل حمل (يدوي أو مكتشَف قبل)

        later_mating = Mating.query.filter(
            Mating.female_id == female.id, Mating.date > mating.date,
            Mating.date <= mating.date + timedelta(days=fs.estrus_return_window_days),
        ).first()
        if later_mating:
            continue  # رجعت للفحل — مؤشر إنها ما حملت من هذا التقريع

        already_confirmed = Pregnancy.query.filter(
            Pregnancy.female_id == female.id, Pregnancy.date >= mating.date, Pregnancy.confirmed.is_(True),
        ).first()
        if already_confirmed:
            continue

        gave_birth_since = Animal.query.filter(
            Animal.mother_id == female.id, Animal.birth_date >= mating.date,
        ).first()
        if gave_birth_since:
            continue  # الدورة خلصت بولادة فعلية أصلاً، ما فيه داعي لمؤشر متأخر

        pregnancy = Pregnancy(
            female_id=female.id, mating_id=mating.id, date=mating.date, confirmed=False,
            notes=(
                f"حمل محتمل — اكتُشف تلقائياً لأن {female.animal_no} ما رجعت للفحل "
                f"خلال {fs.estrus_return_window_days} يوم بعد التقريع بتاريخ {mating.date}. "
                "بانتظار تأكيد الطبيب (فحص سونار أو تشخيص يدوي)."
            ),
        )
        db.session.add(pregnancy)
        db.session.flush()

        task_service.create_suggested_task(
            title=f"🔬 فحص سونار لتأكيد حمل محتمل — {female.animal_no}",
            task_type="pregnancy_sonar_check",
            barn_id=female.barn_id, animal_id=female.id,
            due_date=mating.date + timedelta(days=fs.implicit_pregnancy_sonar_check_days),
            source_type="ImplicitPregnancy", source_id=mating.id,
            notes=pregnancy.notes,
        )
        created.append(pregnancy)

    return created
