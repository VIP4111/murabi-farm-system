"""اختبار بند تحسين الأداء (المهمة المؤجَّلة من فحص "فحص أداء/سرعة
الموقع"): get_alerts() كانت تشغّل 9 دوال توليد مهام كاملة (كل وحدة
فحص جدول كامل) بكل استدعاء — صار فيها حارس زمني قصير
(ALERT_GENERATORS_THROTTLE_MINUTES) يمنع التكرار المفرط لو استُدعيت
عدة مرات خلال دقائق قليلة (نفس فلسفة حارس فحص إشعارات Push الدوري)،
بدون ما يغيّر أي سلوك وظيفي (كل دوال التوليد نفسها idempotent أصلاً)."""
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import FarmSettings


def test_generators_run_once_then_throttled_within_window(app):
    from app.core import alerts_service

    # أبسط طريقة نتحقق فيها من "شُغّلت التسعة أو لا" بدون مونكي-باتش
    # كل استيراد داخلي: نراقب `FarmSettings.last_alert_generators_run`
    # نفسه — لو تحدَّث، يعني الكتلة اشتغلت هذي المرة.
    fs = FarmSettings.get()
    assert fs.last_alert_generators_run is None

    alerts_service.get_alerts()
    first_run = FarmSettings.get().last_alert_generators_run
    assert first_run is not None, "أول استدعاء لازم يشغّل دوال التوليد ويحدّث الحارس"

    alerts_service.get_alerts()
    second_run = FarmSettings.get().last_alert_generators_run
    assert second_run == first_run, "استدعاء ثانٍ خلال نفس الدقائق القليلة ما لازم يعيد تشغيل التوليد"


def test_generators_run_again_after_throttle_window_passes(app):
    from app.core import alerts_service

    alerts_service.get_alerts()
    first_run = FarmSettings.get().last_alert_generators_run

    # نفرض إن آخر تشغيل كان قبل فترة أطول من الحارس — لازم يشتغل من جديد.
    fs = FarmSettings.get()
    fs.last_alert_generators_run = first_run - timedelta(
        minutes=alerts_service.ALERT_GENERATORS_THROTTLE_MINUTES + 1)
    db.session.commit()

    alerts_service.get_alerts()
    second_run = FarmSettings.get().last_alert_generators_run
    assert second_run > first_run, "بعد انتهاء نافذة الحارس، الاستدعاء الجديد لازم يشغّل التوليد من جديد"


def test_get_alerts_still_returns_alerts_normally(app):
    """تصحيح وظيفي بسيط — الحارس الجديد ما لازم يمنع التنبيهات نفسها
    من الحساب والرجوع، بس يمنع إعادة تشغيل دوال التوليد فقط."""
    from app.core import alerts_service
    alerts = alerts_service.get_alerts()
    assert isinstance(alerts, list)
