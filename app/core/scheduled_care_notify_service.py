"""تذكير تيليجرام/بريد فوري لتطعيم/وزن متأخر (بند إضافي 163، المرحلة
د-2؛ وسّع ببند إضافي 167 ليشمل البريد + تعليمات تشغيلية مرفقة) —
نفس منطق `scheduled_care_service` (بند 149) الموجود أصلاً لتوليد
المهام، بس مع إشعار فوري لصاحب الحلال/الدكتور وقت ما مهمة جديدة
فعلاً تتولّد (idempotent أصلاً — يتصفّر بصمت لو المهمة موجودة سلفاً،
فهذا الإشعار ما يتكرر لنفس الحالة).

**بند إضافي 167**: تنبيه "تحصين مستحق" ما عاد يكتفي باسم اللقاح
فقط — يرفق تلقائياً (لو الدواء مرتبط بصنف صيدلية معروف) نفس نص
`MEDICINE_CLASS_GUIDE` (وش هذا النوع من الدواء عموماً) و
`INJECTION_GUIDE` (طريقة الحقن الاسترشادية) الموجودَين أصلاً بشاشة
الصيدلية — نص عام ثابت، مو جرعة أو قرار خاص بهذا الرأس، بنفس مبدأ
"المساعد قرار مو طبيب" المطبَّق بكل النظام."""
from app.core import telegram_service, email_service


def _vaccination_guidance(task) -> str:
    """يرجّع سطور الإرشاد العام (فئة الدواء + طريقة الحقن) لمهمة
    'تحصين مستحق' لو أمكن ربطها بدواء فعلي بالصيدلية عبر آخر تحصين
    مسجَّل لنفس الرأس — نص وصفي بس، فاضي لو ما فيه ربط كافٍ."""
    if task.task_type != "vaccination_due" or not task.animal_id:
        return ""
    from app.models import Vaccination
    from app.health import health_service

    v = (Vaccination.query.filter_by(animal_id=task.animal_id)
         .order_by(Vaccination.date.desc()).first())
    if not v or not v.pharmacy:
        return ""

    lines = []
    class_guide = health_service.medicine_class_guide_for(v.pharmacy.medicine_class)
    if class_guide:
        lines.append(f"    ℹ️ {class_guide['title']}: {class_guide['notes']}")
    injection_guide = health_service.injection_guide_for(v.pharmacy.usage_method)
    if injection_guide:
        lines.append(f"    💉 {injection_guide['title']}: {injection_guide['notes']}")
    return ("\n" + "\n".join(lines)) if lines else ""


def notify_new_care_tasks(tasks: list) -> None:
    if not tasks:
        return
    from app.models import User
    users = [
        u for u in User.query.filter(User.is_active_account.is_(True)).all()
        if u.has_permission("health.manage")
    ]
    if not users:
        return
    lines = [f"- {t.title}{_vaccination_guidance(t)}" for t in tasks[:10]]
    more = f"\n(+{len(tasks) - 10} أكثر)" if len(tasks) > 10 else ""
    subject = f"🗓️ {len(tasks)} مهمة رعاية جديدة مستحقة"
    text = subject + ":\n" + "\n".join(lines) + more
    for user in users:
        if user.telegram_chat_id:
            telegram_service.notify_user(user, text)
        if user.email:
            email_service.notify_user(user, subject, text)
