"""
تقرير "تكلفة الرأس الشهرية" (بند 18 بالمواصفة الرئيسية).

التكلفة = مجموع حركات المالية (شراء + مصروف) لكل شهر، بدون الديون
(دعم خارجي/سداد دين — مو تكلفة تشغيلية حقيقية) وبدون البيع (دخل مو تكلفة).

**بند إضافي 251** — قبل هذا البند، عدد الرؤوس المستخدم بكل شهر كان
العدد النشط الحالي (لحظة توليد التقرير) لكل الأشهر، حتى الماضية منها —
تقريب موثّق بصراحة بالكود والشاشة، لكن غلط فعلياً لو تغيّر حجم القطيع
بين الأشهر. الحل: إعادة بناء عدد الرؤوس الفعلي لأي شهر ماضٍ من بيانات
موجودة أصلاً، بدون أي جدول snapshot جديد:
- تاريخ دخول كل رأس = `birth_date` أو `purchase_date` أو `entry_date`
  (نفس الأولوية المستخدمة بأماكن ثانية بالمشروع، مثل cycle_engine).
- تاريخ خروجه = أقرب حدث خروج فعلي (`CycleEvent.event_type` بيع/نفوق/
  أرشفة) — كل هذي الأحداث تُسجَّل بتاريخ حقيقي وقت وقوعها أصلاً
  (`cycle_engine.sell_animal`/`mark_animal_dead`/`archive_animal`).
رأس يُحسب "موجود" بشهر معيّن لو دخوله كان بذلك الشهر أو قبله، وخروجه
(لو فيه) كان بعده.
"""
from datetime import date
from calendar import monthrange
from app.models import Finance, Animal, CycleEvent

# بند إضافي (2026-08-30) — طلبك الصريح: أسماء الأشهر كانت عربية ثابتة
# بالكود، فلو بدّلت لغة الواجهة لإنجليزي كان اسم الشهر يبقى عربي (ما
# يتحول). الحل: رقم الشهر بدل الاسم — يبقى صحيح بأي لغة بدون أي منطق
# ترجمة إضافي. أُبقيت MONTH_NAMES_AR فارغة الاستخدام محذوفة كليّاً
# ليتضح أنها لم تعد مصدر أي عرض بالواجهة.

_EXIT_EVENT_TYPES = ("sale", "death", "archive")


def _entry_reference_date(animal: Animal) -> date | None:
    return animal.birth_date or animal.purchase_date or animal.entry_date


def build_entry_exit_maps() -> tuple[dict[int, date], dict[int, date]]:
    """يبني خريطتي (دخول، خروج) لكل رأس مرّة وحدة — يُعاد استخدامها
    لحساب عدد الرؤوس لأي عدد من الأشهر بدون استعلام مكرر لكل شهر."""
    entries: dict[int, date] = {}
    for a in Animal.query.all():
        ref = _entry_reference_date(a)
        if ref:
            entries[a.id] = ref

    exits: dict[int, date] = {}
    for ev in CycleEvent.query.filter(CycleEvent.event_type.in_(_EXIT_EVENT_TYPES)).all():
        prev = exits.get(ev.animal_id)
        if prev is None or ev.event_date < prev:
            exits[ev.animal_id] = ev.event_date

    return entries, exits


def _head_count_for_month(month_start: date, month_end: date,
                           entries: dict[int, date], exits: dict[int, date]) -> int:
    """رأس يُحسب لشهر لو كان موجود ولو جزء منه — دخوله قبل أو خلال
    الشهر (entry <= month_end)، وخروجه (لو فيه) ما كان قبل بداية
    الشهر (exit >= month_start). رأس انباع منتصف الشهر يُحسب لذلك
    الشهر (كان موجود جزء منه)، وما يُحسب بالشهر اللي بعده."""
    count = 0
    for animal_id, entry in entries.items():
        if entry > month_end:
            continue
        exit_date = exits.get(animal_id)
        if exit_date is not None and exit_date < month_start:
            continue
        count += 1
    return count


def average_head_count_between(start: date, end: date, *, maps: tuple[dict, dict] | None = None) -> float:
    """متوسط عدد الرؤوس بين تاريخين (بند إضافي 253) — بدل تقسيم
    تكلفة "منذ الدخول" على عدد الرؤوس الحالي (اليوم) بشاشات تحليل
    الرأس الفردي/نقطة التعادل (كانتا تستخدمان `Animal.query.filter_by
    (status="active").count()` مباشرة، غير متسقة مع الحساب الدقيق
    شهر-بشهر اللي صار بالتقرير الشهري ببند 251). يعيد استخدام نفس
    خرائط الدخول/الخروج، بس بمتوسط بدل تفصيل شهري كامل — أخف حسابياً
    (مناسب لصفحة تُفتح لكل رأس بشكل متكرر)، ودقته قريبة جداً من
    الحساب الكامل. `maps`: خرائط (دخول، خروج) جاهزة مسبقاً — تفادي
    إعادة بنائها من الصفر لكل رأس عند استدعائها لعدة رؤوس بنفس الوقت
    (مثال: `break_even_summary`)."""
    if start > end:
        return 0.0
    entries, exits = maps if maps is not None else build_entry_exit_maps()
    counts = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        month_start = date(y, m, 1)
        month_end = date(y, m, monthrange(y, m)[1])
        counts.append(_head_count_for_month(month_start, month_end, entries, exits))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return (sum(counts) / len(counts)) if counts else 0.0


def monthly_cost_per_head(*, months: int = 12) -> list[dict]:
    today = date.today()
    entries, exits = build_entry_exit_maps()

    results = []
    year, month = today.year, today.month
    for i in range(months):
        yy, mm = year, month - i
        while mm <= 0:
            mm += 12
            yy -= 1
        start = date(yy, mm, 1)
        end = date(yy, mm, monthrange(yy, mm)[1])

        total_cost = sum(
            r.amount for r in Finance.query.filter(
                Finance.date >= start, Finance.date <= end,
                Finance.operation_type.in_(("purchase", "expense")),
                Finance.is_cancelled.is_(False),
            ).all()
        )
        head_count = _head_count_for_month(start, end, entries, exits)
        results.append({
            "year": yy, "month": mm, "month_label": f"{mm:02d}/{yy}",
            "total_cost": total_cost, "head_count": head_count,
            "cost_per_head": (total_cost / head_count) if head_count else None,
        })
    return results


def annual_cost_per_head(monthly_rows: list[dict]) -> dict:
    """إجمالي سنوي واحد (بند إضافي، 2026-07-23) — نفس منهجية التوزيع
    بالتساوي على القطيع اللي يستخدمها التقرير الشهري، بس مجموع كل
    الأشهر المعروضة بدفعة وحدة، عشان توزيع المصاريف غير المباشرة
    (إيجار/صيانة/رواتب) يبين بصورة سنوية واحدة زي ما طلبت، مو شهر
    شهر بس.

    **بند إضافي 251**: بعد ما صار عدد الرؤوس متغيّراً شهر لشهر (بدل
    رقم ثابت)، القسمة السنوية تستخدم *متوسط* عدد الرؤوس عبر الأشهر
    المعروضة (مو رقم شهر واحد بس) — أدق تمثيلاً لحجم القطيع الفعلي
    خلال الفترة."""
    total_cost = sum(r["total_cost"] for r in monthly_rows)
    avg_head_count = (sum(r["head_count"] for r in monthly_rows) / len(monthly_rows)) if monthly_rows else 0
    return {
        "total_cost": total_cost, "head_count": round(avg_head_count, 1),
        "cost_per_head": (total_cost / avg_head_count) if avg_head_count else None,
        "months_count": len(monthly_rows),
    }
