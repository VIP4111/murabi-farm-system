from datetime import datetime, timedelta, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class ProcessedTelegramUpdate(db.Model):
    """منع معالجة نفس نبضة Webhook مرتين (بند إضافي 160.1) — تيليجرام
    يعيد إرسال النبضة نفسها لو ردّ السيرفر متأخر (شائع بالخطة المجانية
    على Render، السيرفر ينام بعد فترة خمول ويحتاج ~50 ثانية يصحى)،
    فيوصل نفس الأمر لعدة عمليات worker وكل واحدة ترد بصمة استقلالية —
    نفس مشكلة/حل بند 119 (`RateLimitHit`) بالضبط: تخزين بقاعدة البيانات
    عمداً، مو ذاكرة بايثون داخل العملية."""
    __tablename__ = "processed_telegram_updates"

    update_id = db.Column(db.BigInteger, primary_key=True)
    created_at = db.Column(db.DateTime, default=_now)


def already_processed(update_id) -> bool:
    """يرجّع True لو سبق معالجة هذا update_id — ويسجّله لو أول مرة.
    ينظّف السجلات الأقدم من يوم بنفس الاستدعاء (زي `check_and_record`)."""
    if update_id is None:
        return False
    if ProcessedTelegramUpdate.query.get(update_id) is not None:
        return True
    db.session.add(ProcessedTelegramUpdate(update_id=update_id))
    cutoff = _now() - timedelta(days=1)
    ProcessedTelegramUpdate.query.filter(ProcessedTelegramUpdate.created_at < cutoff).delete()
    db.session.commit()
    return False
