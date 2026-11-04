from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class ServiceToggle(db.Model):
    """
    "مركز تحكم الخدمات" اللي يشوفه المالك بالإعدادات: كل ميزة اختيارية
    (CRM، تعدد الفروع، تعدد اللغات، ...) لها سطر هنا مع حالة تفعيل ونص
    "النشرة" اللي يشرح شروط تفعيلها. الميزة الموقوفة تختفي بالكامل من كل
    واجهات النظام (مو بس تُخفى بصرياً).
    """
    __tablename__ = "service_toggles"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    requirements_note = db.Column(db.Text)  # نص "النشرة" قبل التفعيل
    is_enabled = db.Column(db.Boolean, default=False, nullable=False)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)

    # بند إضافي 214 — مفاتيح ما لها شاشة ولا منطق فعلي بالنظام لين الآن (ما
    # يقرأها أي كود): تفعيلها ما يغيّر شي. بدل ما نخدع المالك بزر "تفعيل"
    # بلا أثر، نعرضها "قيد البناء" ونمنع تبديلها. أول ما تنبني ميزة، نشيل
    # مفتاحها من هنا.
    NOT_BUILT_KEYS = frozenset({"crm", "multi_branch", "multi_language", "suppliers", "genetics"})

    @property
    def is_built(self) -> bool:
        return self.key not in self.NOT_BUILT_KEYS
