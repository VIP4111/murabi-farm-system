"""
مهام يومية تلقائية (بند إضافي 55.1) — فكرة أساسها كود "مقاني"، مبنية هنا
بنفس فلسفة `pregnancy_care_service.py` بالضبط: ما فيه Cron، يُستدعى عند
فتح شاشة التنبيهات، يفحص حالة المزرعة الآن، ويولّد مهمة "مقترحة" واحدة
(تحتاج مراجعة الدكتور — نفس دورة حياة أي مهمة تلقائية بالمشروع، بدون
استثناء) لكل بند تشغيلي يومي أساسي لم تُنشأ له مهمة اليوم أو أمس بعد.

idempotency: عمود `Task.source_id` عدد صحيح (مو نص)، فما نقدر نخزّن مفتاح
مركّب "اسم_البند:التاريخ" مباشرة فيه. نستخدم بدلها تجزئة رقمية ثابتة
(`zlib.crc32`) من نفس المفتاح — نتيجة حتمية، فنفس البند بنفس اليوم يعطي
نفس الرقم دائماً ويمنع التكرار عبر `source_type` ثابت + `source_id`.
"""
import zlib
from datetime import date, timedelta

from app.models import Animal, Disease, Task
from app.team import task_service

SOURCE_TYPE = "DailyHusbandry"


def _source_id(rule_key: str, for_date: date) -> int:
    return zlib.crc32(f"{rule_key}:{for_date.isoformat()}".encode()) & 0x7FFFFFFF


def _build_context() -> dict:
    today = date.today()
    active_animals = Animal.query.filter_by(status="active").all()

    has_newborns = any(
        a.birth_date and (today - a.birth_date).days <= 30 for a in active_animals
    )
    has_weaning_window = any(
        a.birth_date and 45 <= (today - a.birth_date).days <= 110 for a in active_animals
    )
    has_open_disease = Disease.query.filter_by(status="active").count() > 0
    has_recent_purchase = any(
        a.purchase_date and (today - a.purchase_date).days <= 30 for a in active_animals
    )

    return {
        "has_newborns": has_newborns,
        "has_weaning_window": has_weaning_window,
        "has_open_disease": has_open_disease,
        "needs_isolation_review": has_open_disease or has_recent_purchase,
    }


def _rule_definitions(ctx: dict) -> list[dict]:
    defs = [
        {
            "key": "daily_herd_check", "always": True,
            "title": "🔍 فحص يومي للقطيع",
            "notes": "افحص الشهية والاجترار والحركة والتنفس والبراز والعرج والجروح بكل الحظائر.",
        },
        {
            "key": "daily_water_check", "always": True,
            "title": "💧 فحص الماء والأملاح",
            "notes": "تأكد من نظافة المشارب وتوفر ماء نظيف وأملاح مناسبة طوال اليوم.",
        },
        {
            "key": "daily_barn_cleaning", "always": True,
            "title": "🧹 تنظيف المعالف والحظائر",
            "notes": "راجع جفاف الأرضية والتهوية والزحام، ونظّف المعالف والمشارب.",
        },
        {
            "key": "daily_isolation_review", "condition": ctx["needs_isolation_review"],
            "title": "🚧 مراجعة العزل والحجر",
            "notes": "راجع الحيوانات الجديدة أو المريضة في حظيرة العزل قبل خلطها بالقطيع.",
        },
        {
            "key": "daily_newborn_review", "condition": ctx["has_newborns"],
            "title": "🍼 متابعة المواليد والرضاعة",
            "notes": "تأكد من رضاعة اللبأ ونشاط المواليد الجدد (عمر أقل من 30 يوماً).",
        },
        {
            "key": "daily_weaning_review", "condition": ctx["has_weaning_window"],
            "title": "⚖️ مراجعة الفطام والفرز",
            "notes": "راجع الحملان بعمر الفطام (45-110 يوماً) وفرزها حسب الوزن والجنس.",
        },
        {
            "key": "daily_withdrawal_review", "condition": ctx["has_open_disease"],
            "title": "💊 مراجعة الحالات المرضية المفتوحة",
            "notes": "تأكد من عدم وجود علاج مفتوح بلا متابعة، وفترة السحب مسجّلة قبل أي بيع.",
        },
    ]
    return [d for d in defs if d.get("always") or d.get("condition")]


def generate_daily_husbandry_tasks() -> list:
    """يولّد المهام الناقصة لليوم وأمس (تغطية لو فات يوم بدون فتح الشاشة).
    ترجع فقط المهام اللي أُنشئت الآن — تكرار الاستدعاء لاحقاً بنفس اليوم
    يرجّع قائمة فاضية."""
    today = date.today()
    ctx = _build_context()
    rules = _rule_definitions(ctx)
    created = []

    for for_date in (today - timedelta(days=1), today):
        for rule in rules:
            source_id = _source_id(rule["key"], for_date)
            existing = Task.query.filter_by(source_type=SOURCE_TYPE, source_id=source_id).first()
            if existing:
                continue
            task = task_service.create_suggested_task(
                title=rule["title"], task_type="daily_husbandry",
                due_date=for_date, source_type=SOURCE_TYPE, source_id=source_id,
                notes=rule["notes"],
            )
            created.append(task)

    return created
