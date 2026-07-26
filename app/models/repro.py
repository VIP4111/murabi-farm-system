from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class Mating(db.Model):
    """تلقيح عادي (خارج برنامج الشياع التوأمي)."""
    __tablename__ = "matings"

    id = db.Column(db.Integer, primary_key=True)
    female_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=False)
    female = db.relationship("Animal", foreign_keys=[female_id])
    date = db.Column(db.Date, nullable=False)

    male_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=True)
    male = db.relationship("Animal", foreign_keys=[male_id])
    male_note = db.Column(db.String(160))  # لو الفحل خارجي/غير مسجّل بالنظام

    barn_id = db.Column(db.Integer, db.ForeignKey("barns.id"), nullable=True)
    barn = db.relationship("Barn")

    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)


class Pregnancy(db.Model):
    """تشخيص حمل (نتيجة فحص عادي، غير مرتبط ببرنامج شياع)."""
    __tablename__ = "pregnancies"

    id = db.Column(db.Integer, primary_key=True)
    female_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=False)
    female = db.relationship("Animal")
    mating_id = db.Column(db.Integer, db.ForeignKey("matings.id"), nullable=True)
    mating = db.relationship("Mating")

    date = db.Column(db.Date, nullable=False)
    confirmed = db.Column(db.Boolean, default=False, nullable=False)
    sonar_date = db.Column(db.Date)
    embryo_count = db.Column(db.Integer)

    # نتيجة الحمل (بند إضافي 51) — فاضية = لسا متابَع/غير محسوم. إجهاض
    # مسجَّل هنا يشغّل بروتوكول العزل والعيّنات تلقائياً (انظر
    # isolation_service.record_abortion).
    outcome = db.Column(db.String(16))  # abortion فقط حالياً؛ الولادة الناجحة تُقرأ من BirthRecord
    outcome_date = db.Column(db.Date)
    outcome_notes = db.Column(db.Text)

    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)


class TwinEstrusProgram(db.Model):
    """
    برنامج شياع توأمي: بروتوكول متكامل (تزامن شياع + تحفيز هرموني + تلقيح
    مجدول) لزيادة فرصة التوائم. الحقول هنا نسخة مختصرة من النظام القديم
    (اللي كان فيه 60+ حقل إداري) — أبقينا فقط الحقول اللي فعلياً تقود قرارات
    فعلية (جدولة، تقييم أهلية، نتيجة).
    """
    __tablename__ = "twin_estrus_programs"

    id = db.Column(db.Integer, primary_key=True)
    ewe_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=False)
    ewe = db.relationship("Animal", foreign_keys=[ewe_id])

    protocol_name = db.Column(db.String(160))
    supervising_doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=True)
    supervising_doctor = db.relationship("Doctor")

    ram_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=True)
    ram = db.relationship("Animal", foreign_keys=[ram_id])
    ram_note = db.Column(db.String(160))

    start_date = db.Column(db.Date, nullable=False)
    device_insert_planned_at = db.Column(db.Date)
    device_remove_planned_at = db.Column(db.Date)
    expected_estrus_start = db.Column(db.Date)
    expected_estrus_end = db.Column(db.Date)
    mating_window_start = db.Column(db.Date)
    mating_window_end = db.Column(db.Date)
    confirmed_mating_date = db.Column(db.Date)
    pregnancy_check_date = db.Column(db.Date)
    embryo_count_start = db.Column(db.Integer)
    embryo_count_end = db.Column(db.Integer)
    expected_birth_date = db.Column(db.Date)

    eligibility_status = db.Column(db.String(32), default="pending")  # pending/eligible/not_eligible
    status = db.Column(db.String(32), default="active", nullable=False)  # active/completed/cancelled

    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)


class TwinEstrusAttempt(db.Model):
    """محاولة تلقيح ضمن برنامج شياع توأمي (ممكن أكثر من محاولة بنفس البرنامج)."""
    __tablename__ = "twin_estrus_attempts"

    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey("twin_estrus_programs.id"), nullable=False)
    program = db.relationship("TwinEstrusProgram", backref="attempts")

    mating_date = db.Column(db.Date, nullable=False)
    ram_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=True)
    ram = db.relationship("Animal")
    ram_note = db.Column(db.String(160))

    confirmation_status = db.Column(db.String(32), default="pending")  # pending/confirmed/failed
    observed_by = db.Column(db.String(120))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)


class ReproDevice(db.Model):
    """جهاز تكاثر (إسفنجة/جهاز إفراز هرموني داخلي) ضمن برنامج شياع توأمي."""
    __tablename__ = "repro_devices"

    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey("twin_estrus_programs.id"), nullable=False)
    program = db.relationship("TwinEstrusProgram", backref="devices")

    device_type = db.Column(db.String(120), nullable=False)
    trade_name = db.Column(db.String(120))
    inserted_at = db.Column(db.Date, nullable=False)
    inserted_by = db.Column(db.String(120))
    planned_remove_at = db.Column(db.Date)
    actual_remove_at = db.Column(db.Date)
    early_loss = db.Column(db.Boolean, default=False, nullable=False)

    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)


class HormoneInjection(db.Model):
    """حقنة هرمونية ضمن برنامج شياع توأمي."""
    __tablename__ = "hormone_injections"

    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey("twin_estrus_programs.id"), nullable=False)
    program = db.relationship("TwinEstrusProgram", backref="hormone_injections")

    hormone_name = db.Column(db.String(120), nullable=False)
    dose_value = db.Column(db.Float)
    dose_unit = db.Column(db.String(32))
    route = db.Column(db.String(32))
    planned_at = db.Column(db.Date)
    actual_at = db.Column(db.Date)
    given_by = db.Column(db.String(120))

    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)


class SonarResult(db.Model):
    """فحص سونار — ممكن يكون مستقل أو مرتبط ببرنامج شياع توأمي."""
    __tablename__ = "sonar_results"

    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey("twin_estrus_programs.id"), nullable=True)
    program = db.relationship("TwinEstrusProgram", backref="sonar_results")

    ewe_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=False)
    ewe = db.relationship("Animal")

    exam_date = db.Column(db.Date, nullable=False)
    gestation_age_days = db.Column(db.Integer)
    result = db.Column(db.String(32))  # حامل/غير حامل/غير مؤكد
    embryo_count = db.Column(db.Integer)
    heartbeat = db.Column(db.Boolean)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=True)
    doctor = db.relationship("Doctor")
    recheck_date = db.Column(db.Date)

    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)
