import json
from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class AssistantDraftAction(db.Model):
    """مسودة إجراء من إدخال حر نصي/صوتي (بند إضافي 299 — المرحلة ٤ من
    خطة "عقل المزرعة"، الأخيرة). **قاعدة صارمة لا استثناء لها**: صف
    هنا أبداً ما ينفّذ شي بنفسه — التنفيذ الفعلي (استدعاء دالة الخدمة
    الحقيقية زي `animal_service.register_birth`) يصير فقط لما مستخدم
    حقيقي يضغط "اعتماد" (`draft_action_service.confirm_draft`)، وهذا
    الملف يسجّل هويته صراحة بـ`confirmed_by_id` — توثيق كامل: مين
    اقترح (النموذج، مسجَّل بـ`raw_text`)، ومين اعتمد فعلياً (إنسان،
    مسجَّل هنا)، مفصولان تماماً."""
    __tablename__ = "assistant_draft_actions"

    STATUSES = ("pending", "confirmed", "rejected", "expired", "auto_rejected")

    id = db.Column(db.Integer, primary_key=True)

    raw_text = db.Column(db.Text, nullable=False)
    input_source = db.Column(db.String(16), nullable=False, default="text")  # text / voice
    # بند إضافي 312 — فجوة تدقيق حقيقية: مسودة الصورة (بند 305) تحفظ
    # رابط دائم للصورة (`AssistantMessage.image_url`)، بينما مسودة
    # الصوت (بند 299) كانت تحلّل المقطع وترميه — صفر أثر دائم يقدر
    # المستخدم يرجع له لاحقاً يتأكد وش قال بالضبط. نفس مستوى التوثيق.
    audio_url = db.Column(db.String(500), nullable=True)

    parsed_action_type = db.Column(db.String(64))
    parsed_payload_json = db.Column(db.Text)
    summary_ar = db.Column(db.Text)  # ملخص عربي بشري القراءة لبطاقة التأكيد

    status = db.Column(db.String(16), nullable=False, default="pending")
    rejection_reason = db.Column(db.Text)

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    created_at = db.Column(db.DateTime, default=_now)

    # تحسينك الثالث المعتمد — توثيق هوية المعتمِد الفعلي، منفصل تماماً
    # عن `created_by_id` (اللي هو مين *طلب* التسجيل عبر النص/الصوت).
    confirmed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    confirmed_by = db.relationship("User", foreign_keys=[confirmed_by_id])
    decided_at = db.Column(db.DateTime)

    def get_payload(self) -> dict:
        return json.loads(self.parsed_payload_json) if self.parsed_payload_json else {}

    @staticmethod
    def encode_payload(payload: dict) -> str:
        return json.dumps(payload, ensure_ascii=False)
