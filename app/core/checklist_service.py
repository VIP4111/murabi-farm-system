"""محرك دليل المربي المبتدئ والتوجيه اليومي/الأسبوعي (بند إضافي 168).

الفكرة: بدل ما ينتظر المستخدم يسأل المساعد الذكي، تُعرض له تلقائياً
بالصفحة الرئيسية قائمة تحقق قصيرة تتغيّر حسب مرحلة القطيع الفعلية
(`active_stages`) ودوره الوظيفي وهل هو "مبتدئ" أو لا — مو قائمة واحدة
ثابتة للجميع، ومو قائمة انتظار لسؤال يُطرح."""
from datetime import date, timedelta
from app.extensions import db
from app.models import ChecklistItem, ChecklistCompletion, Animal, Pregnancy, Barn


def active_stages() -> set[str]:
    """يفحص حالة القطيع الفعلية حالياً ويرجّع مجموعة المراحل النشطة —
    "عام" و"تجهيز" دائماً نشطتان (كل مزرعة بحاجتهما بغض النظر عن حالة
    القطيع)، البقية تُفعَّل بس لو فيها بيانات فعلية تطابقها الآن."""
    stages = {"general", "prep"}

    if Animal.query.filter_by(status="active", purpose="تسمين").first():
        stages.add("fattening")

    pregnant = (
        Pregnancy.query.filter_by(confirmed=True)
        .join(Animal, Pregnancy.female_id == Animal.id)
        .filter(Animal.status == "active")
        .first()
    )
    if pregnant:
        stages.add("pregnancy")

    from app.core.animal_filters_service import get_filtered
    if get_filtered("ready_to_mate"):
        stages.add("estrus")

    newborn_in_isolation = (
        Animal.query.join(Barn, Animal.barn_id == Barn.id)
        .filter(Barn.barn_type == "عزل", Animal.status == "active")
        .first()
    )
    if newborn_in_isolation:
        stages.add("birth")

    return stages


def _period_key(frequency: str, today: date) -> str:
    if frequency == "daily":
        return today.isoformat()
    if frequency == "weekly":
        start = today - timedelta(days=today.weekday())
        return start.isoformat()
    return "once"


def daily_checklist_for(user, today: date | None = None) -> list[dict]:
    """يرجّع قائمة عناصر الدليل المناسبة لهذا المستخدم الآن: تطابق
    مرحلة نشطة + (دوره الوظيفي أو "all") + (لو "beginner" فقط لمن فعّل
    وسم المبتدئ)، مع حالة الإنجاز الحالية لكل عنصر."""
    today = today or date.today()
    stages = active_stages()
    role_name = user.role.name if user.role else None

    candidate_roles = {"all", role_name}
    if user.is_beginner:
        candidate_roles.add("beginner")

    items = (
        ChecklistItem.query.filter(
            ChecklistItem.is_active.is_(True),
            ChecklistItem.stage.in_(stages),
            ChecklistItem.target_role.in_(candidate_roles),
        )
        .order_by(ChecklistItem.stage, ChecklistItem.sort_order)
        .all()
    )

    result = []
    for item in items:
        period_key = _period_key(item.frequency, today)
        done = ChecklistCompletion.query.filter_by(
            user_id=user.id, checklist_item_id=item.id, period_key=period_key,
        ).first() is not None
        result.append({"item": item, "period_key": period_key, "done": done})
    return result


def toggle_completion(user, item_id: int, today: date | None = None) -> bool:
    """يقلب حالة الإنجاز (لو موجودة يحذفها، لو مو موجودة يضيفها) —
    يرجّع الحالة الجديدة (True = مُنجَز الآن)."""
    item = ChecklistItem.query.get_or_404(item_id)
    today = today or date.today()
    period_key = _period_key(item.frequency, today)
    existing = ChecklistCompletion.query.filter_by(
        user_id=user.id, checklist_item_id=item.id, period_key=period_key,
    ).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return False
    db.session.add(ChecklistCompletion(
        user_id=user.id, checklist_item_id=item.id, period_key=period_key,
    ))
    db.session.commit()
    return True


def onboarding_steps_for(user) -> list[ChecklistItem]:
    """خطوات مسار الترحيب أول دخول — عناصر مرحلة "عام" وتكرار "once"
    المستهدَفة لدور المستخدم (أو "all")، بغض النظر عن `active_stages`
    (الترحيب يظهر مرة واحدة دائماً، مو مشروطاً بحالة القطيع)."""
    role_name = user.role.name if user.role else None
    candidate_roles = {"all", role_name}
    if user.is_beginner:
        candidate_roles.add("beginner")
    return (
        ChecklistItem.query.filter(
            ChecklistItem.is_active.is_(True),
            ChecklistItem.stage == "general",
            ChecklistItem.frequency == "once",
            ChecklistItem.target_role.in_(candidate_roles),
        )
        .order_by(ChecklistItem.sort_order)
        .all()
    )
