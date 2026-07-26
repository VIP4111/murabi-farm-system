from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class ProductionWorkflow(db.Model):
    """
    حالة دورة الإنتاج الحالية لكل حيوان — صف واحد لكل حيوان، يُشتق ويُحدَّث
    تلقائياً من الأحداث الفعلية (CycleEvent) عبر app/core/cycle_engine.py،
    مو من إدخال يدوي. هذا يسمح باكتشاف "انحراف" لو البيانات الفعلية
    اختلفت عن المرحلة المخزّنة.
    """
    __tablename__ = "production_workflows"

    id = db.Column(db.Integer, primary_key=True)
    animal_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=False, unique=True)
    animal = db.relationship("Animal", backref=db.backref("workflow", uselist=False))

    # يُحدَّد مرة واحدة عند إنشاء السجل ولا يُعاد حسابه تلقائياً لاحقاً —
    # حتى لو تغيّر غرض الحيوان بعدين، حسب قرار صاحب النظام.
    route = db.Column(db.String(32), nullable=False)

    current_stage = db.Column(db.Integer, default=1, nullable=False)
    stage_name = db.Column(db.String(64))
    status = db.Column(db.String(32), default="active", nullable=False)  # active/out_of_order/complete
    destiny_decision = db.Column(db.String(32))  # بيع / نفوق طارئ / حذف-أرشفة

    missing_items = db.Column(db.Text)
    out_of_order_count = db.Column(db.Integer, default=0, nullable=False)

    # بيانات تخطيط السوق (تُملأ يدوياً لدعم بوابة مرحلة 5)
    target_sale_date = db.Column(db.Date)
    target_profit_margin = db.Column(db.Float)
    estimated_value = db.Column(db.Float)
    weaning_date = db.Column(db.Date)

    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)


class CycleEvent(db.Model):
    """سجل تدقيق لكل حدث أثّر بدورة إنتاج حيوان — مصدر الحقيقة لإعادة اشتقاق المرحلة."""
    __tablename__ = "cycle_events"

    id = db.Column(db.Integer, primary_key=True)
    animal_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=False)
    animal = db.relationship("Animal")

    event_type = db.Column(db.String(32), nullable=False)
    stage_index = db.Column(db.Integer, nullable=False)
    stage_name = db.Column(db.String(64))

    source_type = db.Column(db.String(32))
    source_id = db.Column(db.Integer)
    event_date = db.Column(db.Date, nullable=False)

    cycle_status = db.Column(db.String(32))
    allowed_stage = db.Column(db.Integer)
    completed_through = db.Column(db.Integer)
    first_blocked_stage = db.Column(db.Integer)
    next_required_step = db.Column(db.String(64))
    next_required_fix = db.Column(db.Text)
    out_of_order_count = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=_now)
