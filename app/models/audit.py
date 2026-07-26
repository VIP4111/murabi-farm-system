from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class AuditLog(db.Model):
    """
    سجل تدقيق دائم — أساس مبدأ "لا شيء يُحذف أو يتغيّر بصمت" اللي اتفقنا
    عليه (حذف المهام، اعتماد البوابات، تعديل الصلاحيات... كلها تُسجَّل هنا).
    """
    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    actor = db.relationship("User")
    action = db.Column(db.String(64), nullable=False)  # مثال: "task.delete"
    entity_type = db.Column(db.String(64))              # مثال: "Task"
    entity_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)
