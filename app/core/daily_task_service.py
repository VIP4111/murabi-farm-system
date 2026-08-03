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
from datetime import date, datetime, timedelta

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
    # الترتيب هنا (بند إضافي 67، 2026-07-28) يطابق التسلسل الميداني
    # المنطقي الفعلي بالحظيرة صباحاً — طلب صريح من المستخدم: تنظيف
    # المعالف/المشارب أولاً (قبل أي شي ثاني تحتاج تكون الحظيرة نظيفة)،
    # بعدها تعبئة الماء وتوفير الأملاح، وأخيراً الفحص اليومي الشامل
    # للقطيع (أدق قيمة بعد ما الحظيرة صارت جاهزة ونظيفة). `sort_order`
    # يحفظ هذا الترتيب فعلياً بشاشة العرض (مو بس بترتيب التوليد الداخلي)
    # — قبل هذا البند كانت الشاشة تعتمد على due_date بس بدون معيار ثانٍ
    # حاسم لو تشارك أكثر من مهمة نفس التاريخ.
    # القوالب الثابتة (بند إضافي 107) — قبل هذا كانت 3 قواعد مكتوبة هنا
    # مباشرة بالكود؛ صارت تُقرأ من `DailyTaskTemplate` (شاشة "مهام العامل
    # التلقائية")، عشان صاحب الحلال/الدكتور يقدر يضيف أو يوقف مهمة يومية
    # بدون أي تعديل كود. المفتاح مبني من رقم القالب نفسه (ثابت عبر الزمن
    # طالما القالب موجود) — يحافظ على idempotency نفسها (`_source_id`).
    from app.models import DailyTaskTemplate
    template_defs = [
        {"key": f"daily_template_{t.id}", "always": True, "title": t.title, "notes": t.notes or ""}
        for t in DailyTaskTemplate.query.filter_by(is_active=True).order_by(DailyTaskTemplate.sort_order).all()
    ]

    defs = template_defs + [
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


EVENING_PREVIEW_HOUR = 18  # الساعة 6 مساءً — من هذا الوقت تفتح مهام الغد مسبقاً


def generate_daily_husbandry_tasks(*, now: datetime | None = None) -> list:
    """يولّد المهام الناقصة لليوم وأمس (تغطية لو فات يوم بدون فتح الشاشة)،
    وابتداءً من الساعة 6 مساءً (بند إضافي 72، بطلب صريح) يولّد مهام الغد
    مسبقاً أيضاً — عشان يفتح المجال للتحضير المسائي بدل ما تنحبس مهام
    الغد لين تبدأ صباحاً. ترجع فقط المهام اللي أُنشئت الآن — تكرار
    الاستدعاء لاحقاً بنفس اليوم/الساعة يرجّع قائمة فاضية."""
    now = now or datetime.now()
    today = now.date()
    ctx = _build_context()
    rules = _rule_definitions(ctx)
    created = []

    target_dates = [today - timedelta(days=1), today]
    if now.hour >= EVENING_PREVIEW_HOUR:
        target_dates.append(today + timedelta(days=1))

    for for_date in target_dates:
        for order, rule in enumerate(rules):
            source_id = _source_id(rule["key"], for_date)
            existing = Task.query.filter_by(source_type=SOURCE_TYPE, source_id=source_id).first()
            if existing:
                continue
            task = task_service.create_suggested_task(
                title=rule["title"], task_type="daily_husbandry",
                due_date=for_date, source_type=SOURCE_TYPE, source_id=source_id,
                notes=rule["notes"], sort_order=order, target_role="worker",
                auto_approve=True,
            )
            created.append(task)

    return created
