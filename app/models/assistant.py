from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class AssistantMessage(db.Model):
    """
    محادثة المساعد الذكي (بند 25 بالمواصفة الرئيسية) — سجل رسائل مستمر
    لكل مستخدم (مو جلسات/محادثات متعددة، نفس فلسفة "لا نبني كل شي دفعة
    وحدة" — لو احتجنا محادثات متعددة لاحقاً يُضاف حقل conversation_id).

    `answered_by` يوثّق مصدر الرد فعلياً (محرك محلي بالكلمات المفتاحية،
    أو Claude API لو المفتاح مُفعّل بـ.env) — مفيد للتشخيص ومعرفة أداء
    المحرك المحلي بمرور الوقت.
    """
    __tablename__ = "assistant_messages"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user = db.relationship("User")

    role = db.Column(db.String(16), nullable=False)  # user / assistant
    content = db.Column(db.Text, nullable=False)

    intent_code = db.Column(db.String(64), nullable=True)
    answered_by = db.Column(db.String(16), nullable=True)  # local / llm / llm_tools / llm_vision

    # صورة مرفقة (بند إضافي 305) — تحليل بصري عبر Gemini (فحص حالة
    # جلدية، قراءة رقم أذن، مطابقة نوع علف...). رابط دائم بس (نفس آلية
    # `cloud_storage_service.save_upload` المستخدمة بأدلة البلاغات)،
    # ما نخزّن البايتات نفسها بالجدول.
    image_url = db.Column(db.String(500), nullable=True)

    created_at = db.Column(db.DateTime, default=_now)
