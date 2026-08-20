"""تنبيهات البيانات الناقصة (بند إضافي 135) — طلبك الصريح: أي حيوان
يُسجَّل (حتى لو حفظته عادي بدون تعبئة كل شي) لازم يطلع له تنبيه بأي
حقل مهم لسا فاضي، مو تجميد الحفظ. الحقول المطلوبة تختلف حسب مصدر
الحيوان (نفس منطقك بالضبط): "الجنس"/"الوزن"/"الغرض" لازمة لأي حيوان
بغض النظر عن مصدره، أما "السعر" فمطلوب للشراء والهدية والرصيد
الافتتاحي فقط (كلها أصول تحتاج تقييم مالي) — مو للمولود بالمزرعة (ما
له سعر شراء أصلاً، تكلفته تُحسب من استهلاك العلف الفعلي عبر تقرير FCR
الموجود أصلاً، بند 48).
"""
import zlib
from datetime import date, datetime

from app.models import Animal, Task
from app.models.animal import AnimalSource
from app.team import task_service

SOURCE_TYPE = "IncompleteAnimalData"

REQUIRED_FIELDS_ALWAYS = ["gender", "weight", "purpose", "color"]
REQUIRED_FIELDS_BY_SOURCE = {
    AnimalSource.PURCHASE: ["price"],
    AnimalSource.GIFT: ["price"],
    AnimalSource.OPENING_BALANCE: ["price"],
}

FIELD_LABELS_AR = {
    "gender": "الجنس", "weight": "الوزن", "purpose": "الغرض (تربية/تسمين/بيع)", "price": "السعر",
    "color": "اللون",
}


def missing_fields(animal: Animal) -> list[str]:
    """يرجّع أسماء الحقول (مفاتيح `FIELD_LABELS_AR`) الفاضية لهذا الرأس
    — حسب مصدره. يُستخدم من التنبيه ومن مولّد المهمة، نفس المنطق بالضبط
    بمكان واحد."""
    required = list(REQUIRED_FIELDS_ALWAYS) + REQUIRED_FIELDS_BY_SOURCE.get(animal.source, [])
    return [f for f in required if not getattr(animal, f)]


def _source_id(animal_id: int) -> int:
    return zlib.crc32(f"{animal_id}".encode()) & 0x7FFFFFFF


def generate_completion_tasks(*, now: datetime | None = None) -> list:
    """مهمة "📋 أكمل بيانات" واحدة بس لكل رأس ناقص (idempotent عبر
    `animal_id` بس، بدون تاريخ — ما نبي نكرّرها كل يوم لنفس الرأس طول
    ما هي مفتوحة أصلاً). تُحل تلقائياً بمجرد ما العامل/الدكتور يفتحها
    ويكمل البيانات فعلياً بشاشة تعديل الحيوان، ثم يعلّمها "تم" يدوياً
    — نفس دورة حياة أي مهمة ثانية بالنظام، بدون آلية إغلاق خاصة."""
    today = (now or datetime.now()).date()
    created = []

    for animal in Animal.query.filter_by(status="active").all():
        missing = missing_fields(animal)
        if not missing:
            continue
        source_id = _source_id(animal.id)
        existing = Task.query.filter(
            Task.source_type == SOURCE_TYPE, Task.source_id == source_id,
            Task.status.in_(task_service.OPEN_TASK_STATUSES),
        ).first()
        if existing:
            continue
        missing_labels = "، ".join(FIELD_LABELS_AR[f] for f in missing)
        task = task_service.create_suggested_task(
            title=f"📋 أكمل بيانات {animal.animal_no} — ناقصها: {missing_labels}",
            task_type="animal_data_completion",
            animal_id=animal.id, barn_id=animal.barn_id,
            due_date=today, source_type=SOURCE_TYPE, source_id=source_id,
            notes=f"الحقول الناقصة: {missing_labels}. أكمّلها من شاشة تعديل الحيوان ثم علّم المهمة منجزة.",
        )
        created.append(task)

    return created
