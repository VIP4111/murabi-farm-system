"""مراجعة "أكواد الخلفية" (استكمال) — نفس ثغرة `farm_today()`/
`farm_now_naive()` لقيناها منسوخة بـ7 مواضع إضافية بمولّدات المهام
التلقائية (كلها تُستدعى بكل زيارة تعرض تنبيهات عبر `alerts_service.
get_alerts()`). **الأخطر بينها**: `feeding_schedule_service.
generate_feeding_tasks` تقارن `schedule.meal_time` (وقت يدخله صاحب
الحلال بتوقيت السعودية، مثلاً 06:00 لوجبة الصباح) مع `datetime.now().
time()` (وقت السيرفر الخام UTC) — يعني كل وجبة كانت تتأخر توليد
مهمتها 3 ساعات كاملة عن موعدها الفعلي، **يومياً وبدون استثناء** (مو
حافة نادرة قرب منتصف الليل زي بقية إصلاحات التوقيت)."""
from datetime import time as time_cls, datetime as dt
from zoneinfo import ZoneInfo

from app.extensions import db
from app.core import feeding_schedule_service
from app.models import Barn
from app.models.barn import BarnFeedingSchedule
from tests.factories import make_barn


def test_feeding_task_generates_at_actual_riyadh_meal_time_not_utc(app, monkeypatch):
    with app.app_context():
        barn = make_barn(barn_no="TIP-FEED-TZ")
        db.session.add(BarnFeedingSchedule(barn_id=barn.id, meal_time=time_cls(6, 0)))
        db.session.commit()

        # 03:00 UTC = 06:00 بالضبط بتوقيت السعودية (UTC+3) — لحظة موعد
        # الوجبة فعلياً. لو الكود يعتمد بالغلط على وقت النظام (UTC هنا)
        # بدل farm_now_naive()، بيقارن 06:00 (الوجبة) مع 03:00 (يظن إنه
        # الوقت الحالي) ويرفض التوليد (الوجبة "لسا ما وصل وقتها").
        fixed_riyadh_6am = dt(2026, 9, 7, 6, 0, tzinfo=ZoneInfo("Asia/Riyadh"))

        class _FixedDateTime(dt):
            @classmethod
            def now(cls, tz=None):
                return fixed_riyadh_6am.astimezone(tz) if tz else fixed_riyadh_6am

        monkeypatch.setattr("app.extensions.datetime", _FixedDateTime)

        created = feeding_schedule_service.generate_feeding_tasks()
        assert created, "مهمة الوجبة ما تولّدت رغم إنها الساعة 6 الصباح بالضبط بتوقيت السعودية"
