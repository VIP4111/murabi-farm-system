"""تحديد معدل الطلبات (بند إضافي 119، آخر نقطة من التحليل الأمني
الثالث) — كان مفقوداً بالكامل على أي مسار غير الدخول (بلاغات، رفع
ملفات) قبل هذا البند؛ عامل مغرور أو حساب مخترَق يقدر يرسل عدد غير
محدود من البلاغات/الملفات بلا أي كبح."""
from datetime import datetime, timedelta, timezone
from flask_babel import gettext as _
from app.extensions import db
from app.models import RateLimitHit


class RateLimitExceeded(Exception):
    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(_("تجاوزت الحد المسموح — حاول بعد %(seconds)s ثانية.", seconds=retry_after_seconds))


def check_and_record(*, user_id: int, key: str, max_calls: int, window_seconds: int) -> None:
    """يفحص عدد الطلبات لنفس (user_id, key) خلال آخر `window_seconds`
    ثانية — لو وصل الحد `max_calls`، يرفع `RateLimitExceeded` بدون
    تسجيل هذي المحاولة (ما تُحتسب من الحد القادم). لو مسموح، يسجّل
    الطلب فوراً (نفس التزامن، عشان طلبين متزامنين ما يتجاوزان الحد
    مع بعض)."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    window_start = now - timedelta(seconds=window_seconds)

    # تنظيف الصفوف القديمة لنفس المستخدم/المفتاح — يمنع تضخّم الجدول
    # بلا داعٍ (احتياط بسيط، مو مجدولة دورية).
    RateLimitHit.query.filter(
        RateLimitHit.user_id == user_id, RateLimitHit.key == key,
        RateLimitHit.created_at < window_start,
    ).delete(synchronize_session=False)

    recent_count = RateLimitHit.query.filter(
        RateLimitHit.user_id == user_id, RateLimitHit.key == key,
        RateLimitHit.created_at >= window_start,
    ).count()

    if recent_count >= max_calls:
        oldest = (RateLimitHit.query.filter(
            RateLimitHit.user_id == user_id, RateLimitHit.key == key,
            RateLimitHit.created_at >= window_start,
        ).order_by(RateLimitHit.created_at).first())
        retry_after = window_seconds
        if oldest and oldest.created_at:
            elapsed = (now - oldest.created_at).total_seconds()
            retry_after = max(1, int(window_seconds - elapsed))
        db.session.commit()  # يحفظ التنظيف حتى لو رفضنا الطلب
        raise RateLimitExceeded(retry_after)

    db.session.add(RateLimitHit(user_id=user_id, key=key, created_at=now))
    db.session.commit()
