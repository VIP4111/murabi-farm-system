from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class PushSubscription(db.Model):
    """اشتراك جهاز/متصفح واحد لإشعارات Push (بند إضافي، طلبك الصريح
    عن الإشعارات مثل الواتساب) — نفس المستخدم ممكن يكون له أكثر من
    اشتراك (جواله + لابتوبه مثلاً)، كل واحد endpoint مستقل يرجعه
    المتصفح وقت `pushManager.subscribe()`."""
    __tablename__ = "push_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    user = db.relationship("User")

    endpoint = db.Column(db.Text, nullable=False, unique=True)
    p256dh = db.Column(db.String(255), nullable=False)
    auth = db.Column(db.String(255), nullable=False)

    created_at = db.Column(db.DateTime, default=_now)


class SentPushAlert(db.Model):
    """سجل التنبيهات المُرسَلة فعلياً كـPush لكل مستخدم (بند إضافي) —
    التنبيهات (`alerts_service.get_alerts`) محسوبة حية بدون تخزين
    (قرار تصميم موثَّق بـ`app/core/scheduler.py`)، فبدون هذا الجدول
    كنا نرسل نفس التنبيه من جديد كل ما تشتغل نقطة الفحص. `alert_key`
    مفتاح ثابت لكل تنبيه (فئته + الحيوان المرتبط لو وجد) — يختلف عن
    نص التنبيه المترجَم (`label`/`detail`) اللي يتغيّر حسب لغة المستخدم."""
    __tablename__ = "sent_push_alerts"
    __table_args__ = (db.UniqueConstraint("user_id", "alert_key", name="uq_sent_push_alert_user_key"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    alert_key = db.Column(db.String(255), nullable=False)
    sent_at = db.Column(db.DateTime, default=_now)
