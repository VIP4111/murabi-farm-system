"""تذكير تيليجرام فوري لتطعيم/وزن متأخر (بند إضافي 163، المرحلة د-2)
— طلبك: نفس منطق `scheduled_care_service` (بند 149) الموجود أصلاً
لتوليد المهام، بس مع إشعار فوري لصاحب الحلال/الدكتور وقت ما مهمة
جديدة فعلاً تتولّد (idempotent أصلاً — يتصفّر بصمت لو المهمة موجودة
سلفاً، فهذا الإشعار ما يتكرر لنفس الحالة)."""
from app.core import telegram_service


def notify_new_care_tasks(tasks: list) -> None:
    if not tasks:
        return
    from app.models import User
    users = [
        u for u in User.query.filter(
            User.telegram_chat_id.isnot(None), User.is_active_account.is_(True)
        ).all()
        if u.has_permission("health.manage")
    ]
    if not users:
        return
    lines = [f"- {t.title}" for t in tasks[:10]]
    more = f"\n(+{len(tasks) - 10} أكثر)" if len(tasks) > 10 else ""
    text = f"🗓️ {len(tasks)} مهمة رعاية جديدة مستحقة:\n" + "\n".join(lines) + more
    for user in users:
        telegram_service.notify_user(user, text)
