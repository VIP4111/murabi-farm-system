"""جدول وجبات العلف لكل حظيرة (بند إضافي 131) — كل حظيرة تحدّد مواعيد
وجباتها لحالها (`BarnFeedingSchedule`، إعداد مستقل لكل حظيرة حسب طلب
صاحب الحلال الصريح). عند وصول موعد الوجبة، يولّد النظام تلقائياً مهمة
واحدة مجمَّعة (توزيع علف + تنظيف معالف + تغيير ماء) للعامل المسؤول عن
الحظيرة — نفس فلسفة `daily_task_service.py` (بدون Cron، توليد عند فتح
شاشة التنبيهات)، لكن بمقارنة وقت (`meal_time`) إضافةً للتاريخ، عكس
`daily_task_service.py` اللي يقارن على مستوى اليوم فقط.

idempotency: `Task.source_id` عدد صحيح، فنبني تجزئة ثابتة
(`zlib.crc32`) من مفتاح "حظيرة:موعد:تاريخ" — نفس الحيلة المستخدمة في
`daily_task_service._source_id`، تضمن مهمة واحدة فقط لكل حظيرة/موعد/يوم
بغض النظر عن عدد مرات استدعاء الدالة."""
import zlib
from datetime import datetime

from app.models import Barn, Task
from app.team import task_service

SOURCE_TYPE = "BarnFeeding"


def _source_id(barn_id: int, schedule_id: int, for_date) -> int:
    return zlib.crc32(f"{barn_id}:{schedule_id}:{for_date.isoformat()}".encode()) & 0x7FFFFFFF


def generate_feeding_tasks(*, now: datetime | None = None) -> list:
    """يولّد مهمة وجبة علف مجمَّعة (علف + تنظيف معالف + تغيير ماء) لكل
    حظيرة عندها جدول وجبات، لكل موعد وصل وقته اليوم ولسا ما انولّدت له
    مهمة. ترجع فقط المهام اللي أُنشئت الآن."""
    now = now or datetime.now()
    today = now.date()
    current_time = now.time()
    created = []

    barns = Barn.query.filter(Barn.feeding_schedules.any()).all()
    for barn in barns:
        for schedule in barn.feeding_schedules:
            if schedule.meal_time > current_time:
                continue
            source_id = _source_id(barn.id, schedule.id, today)
            existing = Task.query.filter_by(source_type=SOURCE_TYPE, source_id=source_id).first()
            if existing:
                continue
            task = task_service.create_suggested_task(
                title=f"🥣 وجبة علف {schedule.meal_time.strftime('%H:%M')} — {barn.barn_name}",
                task_type="feeding_schedule", barn_id=barn.id, due_date=today,
                source_type=SOURCE_TYPE, source_id=source_id,
                notes="توزيع العلف + تنظيف المعالف + تغيير الماء لهذي الوجبة.",
                sort_order=schedule.sort_order, target_role="worker", auto_approve=True,
            )
            created.append(task)

    return created
