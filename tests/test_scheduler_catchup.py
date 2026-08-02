"""بند إضافي 89 (نقطة 6) — تدارك الجدولة اليومية (بند 78) لو الـCron
الداخلي فاته وقته لأن Render المجاني كان نايم. المنطق: أول طلب وارد
باليوم يتأكد من التوليد بنفسه، بدل الاعتماد على توقيت 3 فجراً بالضبط."""
from datetime import date

from app.core.scheduler import catch_up_daily_tasks_before_request
from app.models import FarmSettings, Task
from app.extensions import db


def test_catch_up_generates_tasks_when_not_run_today(app):
    with app.app_context():
        settings = FarmSettings.get()
        assert settings.last_daily_tasks_auto_run is None

        catch_up_daily_tasks_before_request()

        db.session.expire_all()
        settings = FarmSettings.get()
        assert settings.last_daily_tasks_auto_run == date.today()
        assert Task.query.filter_by(source_type="DailyHusbandry").count() > 0


def test_catch_up_skips_if_already_run_today(app):
    with app.app_context():
        settings = FarmSettings.get()
        settings.last_daily_tasks_auto_run = date.today()
        db.session.commit()

        catch_up_daily_tasks_before_request()

        assert Task.query.filter_by(source_type="DailyHusbandry").count() == 0


def test_before_request_hook_not_registered_under_testing_config(app):
    # TESTING=True يوقف تسجيل الـhook أصلاً (نفس نمط init_scheduler) —
    # نتحقق مباشرة إنه مو مسجّل بقائمة before_request functions لفلاسك،
    # بدل الاعتماد على غياب مهام مولَّدة (alerts_service أصلاً يولّد
    # مهام عند الطلب بمناسبات أخرى غير مرتبطة بهذا الـhook).
    hook_names = {
        f.__name__
        for funcs in app.before_request_funcs.values()
        for f in funcs
    }
    assert "_catch_up_daily_tasks" not in hook_names
