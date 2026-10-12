"""منطق التقريع/الحمل (تلقيح، تشخيص حمل، تأكيد حمل) كدوال خدمة مستقلة.

كان هذا المنطق مدفوناً داخل راوتات `app/repro/routes.py` (يعتمد على
`current_user`/`flash`)، فما كان ممكن يستدعيه أي مسار ثاني (وكيل المحادثة
مثلاً) بدون تكراره. الراوتات الآن تستدعي نفس هذي الدوال بالضبط، فالسلوك
واحد من الشاشة اليدوية ومن الوكيل — الفرق الوحيد أن `record_mating_checked`
يفحص بنفسه العمر والقرابة (الراوت يعرضها كنموذج تحذير تفاعلي).
"""
from datetime import date

from flask_babel import gettext as _

from app.extensions import db, farm_today
from app.models import Animal, AuditLog, FarmSettings, Mating, Pregnancy

# حدود منطقية واسعة عمداً (نفس فلسفة validation_service): تمنع خطأ
# كتابة واضح بدون ما ترفض حالة نادرة لكن ممكنة.
MAX_EMBRYO_COUNT = 6
MAX_GESTATION_AGE_DAYS = 165


class CloseRelationError(ValueError):
    """قرابة وراثية موثّقة بين الأنثى والفحل — التجاوز قرار بشري صريح
    (صلاحية مستقلة بالشاشة اليدوية)، ما يتخذه أي مسار آلي."""

    def __init__(self, relation: dict):
        self.relation = relation
        super().__init__(_(
            "بين الأنثى والفحل قرابة وراثية (%(label)s) — سجّل التقريع يدوياً من شاشة التقريع بعد المراجعة.",
            label=relation.get("label", ""),
        ))


def _log(actor_user_id, action, entity_type, entity_id, details=""):
    db.session.add(AuditLog(actor_user_id=actor_user_id, action=action,
                             entity_type=entity_type, entity_id=entity_id, details=details))


def validate_embryo_count(embryo_count) -> None:
    if embryo_count is None:
        return
    if not (0 <= embryo_count <= MAX_EMBRYO_COUNT):
        raise ValueError(_("عدد الأجنة لازم يكون بين 0 و%(max)s.", max=MAX_EMBRYO_COUNT))


def create_mating_row(*, female_id: int, mating_date: date, male_id: int | None = None,
                       male_note: str | None = None, barn_id=None, notes: str | None = None,
                       actor_user_id: int, relation_confirmed: bool = False) -> Mating:
    """الحفظ الفعلي فقط (بدون فحوص التحذير) — يستدعيه الراوت بعد ما يعرض
    تحذيراته التفاعلية، و`record_mating_checked` بعد فحوصه."""
    row = Mating(female_id=female_id, date=mating_date, male_id=male_id, male_note=male_note,
                 barn_id=barn_id or None, notes=notes)
    db.session.add(row)
    db.session.flush()
    _log(actor_user_id, "mating.create", "Mating", row.id,
         details="تم التأكيد رغم تحذير قرابة وراثية" if relation_confirmed else "")
    db.session.commit()

    from app.core.cycle_engine import record_cycle_event
    record_cycle_event(row.female, "mating", source_type="Mating", source_id=row.id, event_date=row.date)
    return row


def record_mating_checked(*, female: Animal, male: Animal | None = None, male_note: str | None = None,
                           mating_date: date | None = None, notes: str | None = None,
                           actor_user_id: int) -> Mating:
    """تقريع بكل الحواجز: أنثى نشطة، فحل ذكر نشط وبعمر كافٍ، بدون قرابة
    وراثية موثّقة (القرابة تُرفض هنا دايماً — التجاوز بالشاشة اليدوية)."""
    from app.core import lineage_service, validation_service

    if female.gender != "أنثى":
        raise ValueError(_("الرأس \"%(no)s\" مو أنثى.", no=female.animal_no))
    if female.status != "active":
        raise ValueError(_("الحيوان \"%(no)s\" مو نشط (مباع أو نافق).", no=female.animal_no))
    mating_date = mating_date or farm_today()
    validation_service.validate_not_future_date(mating_date, field_label=_("تاريخ التقريع"))

    if male is not None:
        if male.gender != "ذكر":
            raise ValueError(_("الرأس \"%(no)s\" مو ذكر.", no=male.animal_no))
        if male.status != "active":
            raise ValueError(_("الحيوان \"%(no)s\" مو نشط (مباع أو نافق).", no=male.animal_no))
        if male.birth_date:
            age_days = (farm_today() - male.birth_date).days
            if age_days < FarmSettings.get().min_male_breeding_age_days:
                raise ValueError(_("هذا الفحل غير متاح للتقريع (عمره أقل من الحد الأدنى المسموح)"))
        relation = lineage_service.relationship_warning(female.id, male.id)
        if relation:
            raise CloseRelationError(relation)
    elif not (male_note or "").strip():
        raise ValueError(_("حدّد رقم الفحل أو اكتب وصفه إن كان خارجياً."))

    return create_mating_row(
        female_id=female.id, mating_date=mating_date, male_id=male.id if male else None,
        male_note=(male_note or None), notes=notes, actor_user_id=actor_user_id,
    )


def create_pregnancy_row(*, female_id: int, pregnancy_date: date, mating_id=None, confirmed: bool = False,
                          sonar_date: date | None = None, embryo_count: int | None = None,
                          notes: str | None = None, actor_user_id: int) -> Pregnancy:
    row = Pregnancy(female_id=female_id, mating_id=mating_id or None, date=pregnancy_date,
                    confirmed=bool(confirmed), sonar_date=sonar_date, embryo_count=embryo_count, notes=notes)
    db.session.add(row)
    db.session.flush()
    _log(actor_user_id, "pregnancy.create", "Pregnancy", row.id)
    db.session.commit()

    from app.core.cycle_engine import record_cycle_event
    record_cycle_event(row.female, "pregnancy", source_type="Pregnancy", source_id=row.id, event_date=row.date)
    return row


def latest_open_pregnancy(female: Animal) -> Pregnancy | None:
    """آخر حمل للأنثى لسا ما له نتيجة (إجهاض) — أساس "أكّد حملها"."""
    return (Pregnancy.query.filter_by(female_id=female.id, outcome=None)
            .order_by(Pregnancy.date.desc(), Pregnancy.id.desc()).first())


def record_pregnancy_checked(*, female: Animal, confirmed: bool = False, embryo_count: int | None = None,
                              sonar_date: date | None = None, pregnancy_date: date | None = None,
                              notes: str | None = None, actor_user_id: int) -> Pregnancy:
    from app.core import validation_service

    if female.gender != "أنثى":
        raise ValueError(_("الرأس \"%(no)s\" مو أنثى.", no=female.animal_no))
    if female.status != "active":
        raise ValueError(_("الحيوان \"%(no)s\" مو نشط (مباع أو نافق).", no=female.animal_no))
    pregnancy_date = pregnancy_date or farm_today()
    validation_service.validate_not_future_date(pregnancy_date, field_label=_("تاريخ تشخيص الحمل"))
    validate_embryo_count(embryo_count)

    existing = latest_open_pregnancy(female)
    if existing and (pregnancy_date - existing.date).days <= MAX_GESTATION_AGE_DAYS:
        raise ValueError(_("للأنثى \"%(no)s\" حمل مسجَّل أصلاً — استخدم تأكيد الحمل بدل تسجيل جديد.",
                           no=female.animal_no))

    # ربط تلقائي بآخر تقريع للأنثى ضمن مدة حمل منطقية (يفيد حساب موعد الولادة)
    mating = (Mating.query.filter(Mating.female_id == female.id, Mating.date <= pregnancy_date)
              .order_by(Mating.date.desc(), Mating.id.desc()).first())
    if mating and (pregnancy_date - mating.date).days > MAX_GESTATION_AGE_DAYS:
        mating = None

    return create_pregnancy_row(
        female_id=female.id, pregnancy_date=pregnancy_date, mating_id=mating.id if mating else None,
        confirmed=confirmed, sonar_date=sonar_date, embryo_count=embryo_count, notes=notes,
        actor_user_id=actor_user_id,
    )


def confirm_pregnancy(pregnancy: Pregnancy, *, actor_user_id: int) -> Pregnancy:
    """تأكيد حمل مسجَّل "غير مؤكَّد" (بند إضافي 283) — هو اللي يُدخله
    بعدّاد الحوامل (`confirmed=True` حصراً)."""
    if pregnancy.confirmed:
        raise ValueError(_("هذا الحمل مؤكَّد أصلاً."))
    if pregnancy.outcome:
        raise ValueError(_("هذا الحمل مسجَّل له نتيجة إجهاض — ما ينفع يُأكَّد."))
    pregnancy.confirmed = True
    _log(actor_user_id, "pregnancy.confirm", "Pregnancy", pregnancy.id)
    db.session.commit()
    return pregnancy
