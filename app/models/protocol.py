from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class TreatmentProtocol(db.Model):
    """قالب بروتوكول علاج جاهز (بند إضافي 52) — سلسلة خطوات مجدولة (كل
    خطوة = دواء محدد من الصيدلية + كمية + يوم استحقاق نسبي من بداية
    التطبيق). التطبيق الفعلي (`protocol_service.apply_protocol`) يولّد
    مهمة "علاج مخطَّط" واحدة لكل خطوة، بنفس آلية بند 50 بالضبط — فالخصم
    من المخزون وفترة السحب (الأطول بين كل أدوية البروتوكول) يُطبَّقان
    تلقائياً بلا كود إضافي عند "تأكيد التنفيذ" لكل خطوة (`animal_under_
    withdrawal` أصلاً يأخذ أقصى فترة سحب فعّالة عبر كل السجلات)."""
    __tablename__ = "treatment_protocols"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text)

    # ربط اختياري بمرض من مرجع المساعد التشخيصي — لو معبّى، شاشة نتيجة
    # التشخيص تعرض زر "طبّق هذا البروتوكول" مباشرة لأعلى احتمال مطابق،
    # بدون ما يمنع تطبيق أي بروتوكول يدوياً من أي شاشة حيوان بغض النظر
    # عن التشخيص.
    disease_type_id = db.Column(db.Integer, db.ForeignKey("disease_types.id"), nullable=True)
    disease_type = db.relationship("DiseaseType")

    status = db.Column(db.String(16), default="active", nullable=False)  # active/inactive
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=_now)

    steps = db.relationship("TreatmentProtocolStep", back_populates="protocol",
                             order_by="TreatmentProtocolStep.day_offset",
                             cascade="all, delete-orphan")


class TreatmentProtocolStep(db.Model):
    """خطوة واحدة بالبروتوكول — دواء محدد من الصيدلية (قرارك الصريح: مو
    فئة عامة)، عشان معاينة المخزون بشاشة تفصيل المهمة (`task_rich_context`،
    بند 50) تبقى دقيقة قبل التطبيق."""
    __tablename__ = "treatment_protocol_steps"

    id = db.Column(db.Integer, primary_key=True)
    protocol_id = db.Column(db.Integer, db.ForeignKey("treatment_protocols.id"), nullable=False)
    protocol = db.relationship("TreatmentProtocol", back_populates="steps")

    day_offset = db.Column(db.Integer, nullable=False, default=0)  # نسبي من تاريخ بداية التطبيق
    step_title = db.Column(db.String(160), nullable=False)

    pharmacy_id = db.Column(db.Integer, db.ForeignKey("pharmacy.id"), nullable=False)
    pharmacy = db.relationship("Pharmacy")
    quantity = db.Column(db.Float, nullable=False)
    treatment_kind = db.Column(db.String(16), nullable=False)  # vet_visit / disease / vaccination

    notes = db.Column(db.Text)


class ProtocolApplication(db.Model):
    """أثر تطبيق بروتوكول على رأس محدد بتاريخ معيّن — المرساة اللي تربط
    كل مهام الخطوات المولَّدة (`Task.source_type='ProtocolApplication'`)
    ببعضها، بنفس نمط `batch_siblings` الموجود أصلاً (بند 50) بدون أي
    تعديل عليه."""
    __tablename__ = "protocol_applications"

    id = db.Column(db.Integer, primary_key=True)
    protocol_id = db.Column(db.Integer, db.ForeignKey("treatment_protocols.id"), nullable=False)
    protocol = db.relationship("TreatmentProtocol")
    animal_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=False)
    animal = db.relationship("Animal")

    start_date = db.Column(db.Date, nullable=False)
    applied_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=_now)
