from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class DiseaseType(db.Model):
    """
    قائمة الأمراض الشائعة (بند إضافي، 2026-07-23) — أسماء جاهزة لتسريع
    إدخال "اسم المرض" بشاشة تسجيل حالة مرضية (Disease.disease_name يبقى
    نص حر بالجدول — هذا مرجع اقتراحات بس، مو قيد صارم، فأي مرض غير
    مذكور هنا يُكتب يدوياً عادي). قابلة للتوسيع من المالك/الدكتور
    (`medical_options.manage`) بدون أي تعديل كود — **أسماء فقط، بدون أي
    توصية علاج أو جرعة** (قاعدة "المساعد قرار مو طبيب" تنطبق هنا بالضبط).
    """
    __tablename__ = "disease_types"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), unique=True, nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)


class Symptom(db.Model):
    """عرض/علامة مرضية (بند إضافي، 2026-07-24) — عنصر أساسي بشجرة التشخيص
    التفاعلية (`/health/diagnose`). `is_primary` يحدد العرض اللي يبدأ
    منه التشخيص (حرارة/إسهال/عرج...)؛ بقية الأعراض تظهر كأسئلة متابعة
    ثنائية (نعم/لا). قابلة للتوسيع من `medical_options.manage` بدون كود،
    نفس فلسفة `DiseaseType`."""
    __tablename__ = "symptoms"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), unique=True, nullable=False)
    is_primary = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=_now)


class DiseaseSymptomLink(db.Model):
    """ربط مرض بعرض + وزن دلالته (1=محتمل، 2=شائع، 3=دليل قوي) — أساس
    محرك التوصية بالتشخيص (بند إضافي، 2026-07-24): يجمع أوزان الأعراض
    المطابقة لكل مرض ويرتّبها. **مرجع مطابقة أنماط مبني على معرفة عامة
    موثّقة لأمراض شائعة**، مو تشخيص مخبري مؤكَّد — يبقى قيد "active" غير
    مغلق لين ما يراجعه الدكتور ويوثّق تعافي فعلي (`Disease.status`،
    قاعدة 12.3 الموجودة أصلاً بالمشروع)."""
    __tablename__ = "disease_symptom_links"

    id = db.Column(db.Integer, primary_key=True)
    disease_type_id = db.Column(db.Integer, db.ForeignKey("disease_types.id"), nullable=False)
    disease_type = db.relationship("DiseaseType", backref="symptom_links")
    symptom_id = db.Column(db.Integer, db.ForeignKey("symptoms.id"), nullable=False)
    symptom = db.relationship("Symptom")
    weight = db.Column(db.Integer, default=1, nullable=False)

    __table_args__ = (db.UniqueConstraint("disease_type_id", "symptom_id", name="uq_disease_symptom"),)


class VetVisit(db.Model):
    __tablename__ = "vet_visits"

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    doctor = db.relationship("Doctor")
    animal_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=False)
    animal = db.relationship("Animal")

    diagnosis = db.Column(db.String(255))
    pharmacy_id = db.Column(db.Integer, db.ForeignKey("pharmacy.id"))
    pharmacy = db.relationship("Pharmacy")
    quantity_used = db.Column(db.Float)

    cost = db.Column(db.Float, default=0)
    payment_status = db.Column(db.String(32), default="unpaid")
    notes = db.Column(db.Text)

    # فترة السحب المحسوبة تلقائياً من دواء الصيدلية (انظر health_service.py)
    withdrawal_until = db.Column(db.Date, nullable=True)

    created_at = db.Column(db.DateTime, default=_now)


class Disease(db.Model):
    __tablename__ = "diseases"

    id = db.Column(db.Integer, primary_key=True)
    animal_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=False)
    animal = db.relationship("Animal")

    disease_name = db.Column(db.String(160), nullable=False)
    date = db.Column(db.Date, nullable=False)
    severity = db.Column(db.String(32))
    status = db.Column(db.String(32), default="active", nullable=False)  # active/closed

    pharmacy_id = db.Column(db.Integer, db.ForeignKey("pharmacy.id"))
    pharmacy = db.relationship("Pharmacy")
    # كانت تُجمَع بالفورم وتُستخدم بس لخصم المخزون بدون ما تُخزَّن — سدّينا
    # الفجوة (بند إضافي، 2026-07-23): لازم تبقى محفوظة لحساب التكلفة
    # الفردية للرأس والرجوع لسجل الجرعات الفعلي لاحقاً.
    quantity_used = db.Column(db.Float)
    treatment_cost = db.Column(db.Float, default=0)

    # سجل مرضي مفتوح يبقى مفتوح لين ما يُوثَّق تعافي أو قرار طبيب صريح —
    # ما يُغلق لمجرد انتهاء الجرعات (قاعدة 12.3 بالمواصفة).
    recovery_note = db.Column(db.Text)
    closed_at = db.Column(db.DateTime)
    closed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    closed_by = db.relationship("User")

    withdrawal_until = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=_now)


class Vaccination(db.Model):
    __tablename__ = "vaccinations"

    id = db.Column(db.Integer, primary_key=True)
    animal_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=False)
    animal = db.relationship("Animal")

    vaccine_name = db.Column(db.String(160), nullable=False)
    date = db.Column(db.Date, nullable=False)
    next_due_date = db.Column(db.Date)

    pharmacy_id = db.Column(db.Integer, db.ForeignKey("pharmacy.id"))
    pharmacy = db.relationship("Pharmacy")
    # ماكانا موجودين إطلاقاً — التطعيم ماله أي تتبّع تكلفة رغم إنه يستهلك
    # دواء من نفس الصيدلية (بند إضافي، 2026-07-23).
    quantity_used = db.Column(db.Float)
    cost = db.Column(db.Float, default=0)

    withdrawal_until = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=_now)
