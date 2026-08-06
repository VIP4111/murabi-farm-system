"""فرز الحظائر حسب الحالة الفسيولوجية (بند إضافي 133) — امتداد لآلية
"نقل لحظيرة الحوامل" الموجودة أصلاً (`animal_service._register_pregnancy_intake`
+ `task_service._move_to_pregnant_barn`) اللي كانت تشتغل بحالة وحدة بس
(إعلان الحمل وقت الشراء). هذي الآلية تغطي بقية الحالات: أي رأس حمله
وصل مرحلته المتأخرة (نفس نافذة `pregnancy_care_service.py` بالضبط)
أو صار مرضع (نفس تعريف فلتر "المرضعات" بـ`animal_filters_service.py`)،
وحظيرته الحالية مو من النوع المناسب (`Barn.barn_type == "حامل - الشهور الأخيرة"`
أو `"رضاعة"`) — تتولّد له مهمة مقترحة تنقله، تحتاج اعتماد الدكتور
(مو auto_approve، لأنه قرار يمس حيوان مو مجرد تنظيف روتيني).

اتجاه واحد بس (بطلبك الصريح): نفحص "الرأس اللي المفروض ينتقل" — ما
نفحص عكسها ("رأس بحظيرة مو مستحقها")، تفادياً لتنبيهات كاذبة لرؤوس
انتقلت توّها تحضيراً.

idempotency: نفس حيلة `daily_task_service.py` (`zlib.crc32` من مفتاح
حظيرة/رأس/تاريخ)، بدون Cron — يُستدعى عند فتح شاشة التنبيهات."""
import zlib
from datetime import date, datetime, timedelta

from app.models import Animal, Barn, FarmSettings, Pregnancy, Task
from app.core.animal_filters_service import NURSING_MAX_CHILD_AGE_DAYS
from app.team import task_service

SOURCE_TYPE_PREFIX = "BarnPhysiologyMove"


def _source_type(target_barn_type: str) -> str:
    """يشفّر نوع الحظيرة الهدف داخل `source_type` نفسه (بدل عمود جديد)
    — نفس الحيلة، عشان `task_service._move_barn_physiology` يقدر يعرف
    لأي حظيرة ينقل الرأس فعلياً وقت إنجاز المهمة، بدون أي تعديل بجدول
    Task."""
    return f"{SOURCE_TYPE_PREFIX}:{target_barn_type}"


def _source_id(animal_id: int, target_barn_type: str, for_date: date) -> int:
    return zlib.crc32(f"{animal_id}:{target_barn_type}:{for_date.isoformat()}".encode()) & 0x7FFFFFFF


def _late_pregnancy_animal_ids(today: date) -> set[int]:
    fs = FarmSettings.get()
    ids = set()
    for p in Pregnancy.query.filter_by(confirmed=True).all():
        if p.outcome:
            continue
        animal = p.female
        if not animal or animal.status != "active":
            continue
        base_date = p.mating.date if p.mating else p.date
        expected_birth = base_date + timedelta(days=fs.gestation_days)
        trigger_date = expected_birth - timedelta(days=fs.pre_birth_feed_change_days)
        if trigger_date <= today <= expected_birth:
            ids.add(animal.id)
    return ids


def _nursing_animal_ids(today: date) -> set[int]:
    cutoff = today - timedelta(days=NURSING_MAX_CHILD_AGE_DAYS)
    return {
        a.mother_id for a in Animal.query.filter(
            Animal.mother_id.isnot(None), Animal.birth_date >= cutoff, Animal.species == "sheep_goat",
        ).all()
    }


def generate_barn_move_tasks(*, now: datetime | None = None) -> list:
    """يولّد مهمة "🔀 انقل" لكل رأس وصل حالة (حامل بالشهور الأخيرة/
    رضاعة) وحظيرته الحالية مو من النوع المطابق — بشرط وجود حظيرة فعلية
    بهذا النوع أصلاً (بدون كذا ما فيه وجهة ننقل لها). ترجع فقط المهام
    اللي أُنشئت الآن."""
    today = (now or datetime.now()).date()
    created = []

    targets = {
        "حامل - الشهور الأخيرة": _late_pregnancy_animal_ids(today),
        "رضاعة": _nursing_animal_ids(today),
    }

    for target_barn_type, animal_ids in targets.items():
        if not animal_ids:
            continue
        target_barn = Barn.query.filter_by(barn_type=target_barn_type).order_by(Barn.id).first()
        if not target_barn:
            continue
        for animal_id in animal_ids:
            animal = Animal.query.get(animal_id)
            if not animal or animal.barn_id == target_barn.id:
                continue
            source_type = _source_type(target_barn_type)
            source_id = _source_id(animal_id, target_barn_type, today)
            existing = Task.query.filter_by(source_type=source_type, source_id=source_id).first()
            if existing:
                continue
            task = task_service.create_suggested_task(
                title=f"🔀 انقل {animal.animal_no} لحظيرة {target_barn.barn_name} ({target_barn_type})",
                task_type="barn_physiology_move",
                animal_id=animal.id, barn_id=animal.barn_id,
                due_date=today, source_type=source_type, source_id=source_id,
                notes=(
                    f"حالة الرأس الحالية تستدعي حظيرة \"{target_barn_type}\" — حظيرته الحالية غير مطابقة. "
                    "إنجاز هذي المهمة ينقلها فعلياً لتلك الحظيرة."
                ),
            )
            created.append(task)

    return created
