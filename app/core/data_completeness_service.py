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
from flask_babel import lazy_gettext as _l

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

# بند إضافي (2026-08-30) — طلبك: "ابحث عن فجوات في الترجمة في حساب
# الدكتور". كانت هذي القيم نصاً عربياً خاماً غير قابل للترجمة —
# صارت _l() (نفس نمط TASK_TYPE_LABELS_AR بـapp/__init__.py).
FIELD_LABELS_AR = {
    "gender": _l("الجنس"), "weight": _l("الوزن"), "purpose": _l("الغرض (تربية/تسمين/بيع)"),
    "price": _l("السعر"), "color": _l("اللون"),
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

    active_animals = Animal.query.filter_by(status="active").all()
    animals_with_missing = [a for a in active_animals if missing_fields(a)]
    # بند إصلاح أداء (بحث "مشاكل تشغيلية") — كان فحص "فيه مهمة مفتوحة
    # أصلاً؟" يسوي استعلام Task منفصل *لكل رأس ناقص على حدة*ـ، تُستدعى
    # هذي الدالة بكل زيارة تعرض تنبيهات (الرئيسية/سجل الحيوانات/التنبيهات).
    # الإصلاح: استعلام واحد يجيب كل source_id عنده مهمة مفتوحة من هذا
    # المصدر دفعة وحدة، بدل استعلام لكل رأس.
    source_ids = [_source_id(a.id) for a in animals_with_missing]
    open_source_ids = {
        row[0] for row in
        Task.query.filter(
            Task.source_type == SOURCE_TYPE, Task.source_id.in_(source_ids),
            Task.status.in_(task_service.OPEN_TASK_STATUSES),
        ).with_entities(Task.source_id).all()
    } if source_ids else set()

    for animal in animals_with_missing:
        missing = missing_fields(animal)
        source_id = _source_id(animal.id)
        if source_id in open_source_ids:
            continue
        missing_labels = "، ".join(str(FIELD_LABELS_AR[f]) for f in missing)
        task = task_service.create_suggested_task(
            title=f"📋 أكمل بيانات {animal.animal_no} — ناقصها: {missing_labels}",
            task_type="animal_data_completion",
            animal_id=animal.id, barn_id=animal.barn_id,
            due_date=today, source_type=SOURCE_TYPE, source_id=source_id,
            notes=f"الحقول الناقصة: {missing_labels}. أكمّلها من شاشة تعديل الحيوان ثم علّم المهمة منجزة.",
        )
        created.append(task)

    return created
