"""
خدمة "قوائم الحلال المفلترة" (البند 8 بالمواصفة الرئيسية).

المصطلحات (البهم، المقرعات، الدافع/غير دافع...) ماكان لها تعريف رقمي دقيق
بالمواصفة الأصلية — هذي تعريفات اجتهادية مبنية على المعنى الشائع بإدارة
الحلال، موثّقة بالتفصيل هنا وبكل فلتر بالواجهة، وقابلة للتعديل لو عندك
تعريف مختلف:

- البهم: عمرها أقل من 180 يوم (6 أشهر) — يحتاج `birth_date` مسجّل.
- قريب الولادة: حمل مؤكد وتاريخ الولادة المتوقع (تاريخ التقريع/التشخيص +
  مدة الحمل من الإعدادات) خلال 30 يوم القادمة.
- المقرعات: تقريع مسجّل خلال آخر (مدة الحمل) يوم، بغض النظر عن تأكيد الحمل.
- المرضعات: عندها مولود عمره أقل من 90 يوم (نفس عتبة بوابة الفطام
  بمحرك الدورة — app/core/cycle_engine.py).
- الدافع: أنثى عمرها سنة فأكثر وعندها ولادة واحدة على الأقل خلال آخر 400 يوم.
- غير دافع: أنثى عمرها سنة فأكثر بدون أي ولادة خلال آخر 400 يوم.
- جاهزة للتقريع (بند 10.4): أنثى نشطة بلغت "أقل عمر للتقريع الأول"، مو
  حامل حالياً (آخر حمل مؤكد إلها انتهى بولادة)، ما عندها تقريع مسجّل
  خلال مدة الحمل الأخيرة (يعني مو بمسار تقريع نشط أصلاً)، عدّت "أقل فترة
  راحة بعد الولادة" من آخر ولادة لها (لو عندها ولادات سابقة)، وبدون
  أمراض مفتوحة حالياً. القيمتان (أقل عمر، أقل فترة راحة) من الإعدادات.

**بند 23**: كل الفلاتر المبنية على بيولوجيا تكاثر المجترات (البهم،
المقرعات، قريب الولادة، المرضعات، دافع/غير دافع، جاهزة للتقريع) تستثني
النعام صراحة — لها فلتر منفصل "النعام" وتفقيسها له صفحته الخاصة
`app/ostrich/`.
"""
from datetime import date, timedelta
from flask_babel import lazy_gettext as _l
from app.models import Animal, Mating, Pregnancy, Disease, FarmSettings

LAMB_MAX_AGE_DAYS = 180
NURSING_MAX_CHILD_AGE_DAYS = 90
BREEDING_ADULT_MIN_AGE_DAYS = 365
PRODUCTIVE_WINDOW_DAYS = 400
NEAR_BIRTH_WINDOW_DAYS = 30


def _age_days(animal: Animal) -> int | None:
    if not animal.birth_date:
        return None
    return (date.today() - animal.birth_date).days


def _active_query():
    return Animal.query.filter_by(status="active")


def _ruminant_query():
    """الفلاتر المبنية على بيولوجيا التكاثر (حمل/تقريع/فطام...) ما تنطبق
    إلا على "حلال" (بند 23 + توسعة إضافة الفصائل 2026-07-28) — النعام
    وأي فصيلة جديدة تُضاف لاحقاً (ما بُني لها نظام تكاثر مخصّص بعد)
    مستثناة هنا صراحة بأمان."""
    return _active_query().filter(Animal.species == "sheep_goat")


def _ostriches():
    return _active_query().filter_by(species="ostrich").order_by(Animal.animal_no).all()


def _lambs():
    return [a for a in _ruminant_query().all()
            if (d := _age_days(a)) is not None and d < LAMB_MAX_AGE_DAYS]


def _males():
    return _active_query().filter_by(gender="ذكر").order_by(Animal.animal_no).all()


def _fattening():
    return _active_query().filter_by(purpose="تسمين").order_by(Animal.animal_no).all()


def _dead():
    return Animal.query.filter_by(status="dead").order_by(Animal.animal_no).all()


def _mated():
    gestation_days = FarmSettings.get().gestation_days
    cutoff = date.today() - timedelta(days=gestation_days)
    female_ids = {
        m.female_id for m in Mating.query.filter(Mating.date >= cutoff).all()
    }
    return [a for a in _ruminant_query().filter(Animal.id.in_(female_ids)).all()] if female_ids else []


def _near_birth():
    gestation_days = FarmSettings.get().gestation_days
    today = date.today()
    window_end = today + timedelta(days=NEAR_BIRTH_WINDOW_DAYS)
    rows = Pregnancy.query.filter_by(confirmed=True).all()
    female_ids = set()
    for p in rows:
        base_date = p.mating.date if p.mating else p.date
        expected = base_date + timedelta(days=gestation_days)
        if today <= expected <= window_end:
            female_ids.add(p.female_id)
    return _ruminant_query().filter(Animal.id.in_(female_ids)).all() if female_ids else []


def _nursing():
    """النعام طيور — ما "ترضع" بيولوجياً، فمستثناة من هذا الفلتر عمداً."""
    cutoff = date.today() - timedelta(days=NURSING_MAX_CHILD_AGE_DAYS)
    mother_ids = {
        a.mother_id for a in Animal.query.filter(
            Animal.mother_id.isnot(None), Animal.birth_date >= cutoff, Animal.species == "sheep_goat",
        ).all()
    }
    return _ruminant_query().filter(Animal.id.in_(mother_ids)).all() if mother_ids else []


def _breeding_adult_females():
    cutoff_birth = date.today() - timedelta(days=BREEDING_ADULT_MIN_AGE_DAYS)
    return [
        a for a in _ruminant_query().filter_by(gender="أنثى").all()
        if a.birth_date and a.birth_date <= cutoff_birth
    ]


def _productive_split():
    since = date.today() - timedelta(days=PRODUCTIVE_WINDOW_DAYS)
    productive, unproductive = [], []
    for female in _breeding_adult_females():
        has_recent_birth = Animal.query.filter(
            Animal.mother_id == female.id, Animal.birth_date >= since,
        ).count() > 0
        (productive if has_recent_birth else unproductive).append(female)
    return productive, unproductive


def _is_currently_pregnant(female: Animal) -> bool:
    last_pregnancy = (
        Pregnancy.query.filter_by(female_id=female.id, confirmed=True)
        .order_by(Pregnancy.date.desc()).first()
    )
    if not last_pregnancy:
        return False
    gave_birth_since = Animal.query.filter(
        Animal.mother_id == female.id, Animal.birth_date >= last_pregnancy.date,
    ).count() > 0
    return not gave_birth_since


def _has_active_mating(female: Animal) -> bool:
    gestation_days = FarmSettings.get().gestation_days
    cutoff = date.today() - timedelta(days=gestation_days)
    last_mating = (
        Mating.query.filter_by(female_id=female.id).filter(Mating.date >= cutoff)
        .order_by(Mating.date.desc()).first()
    )
    return last_mating is not None


def _ready_to_mate():
    fs = FarmSettings.get()
    today = date.today()
    result = []
    for female in _ruminant_query().filter_by(gender="أنثى").all():
        age = _age_days(female)
        if age is None or age < fs.min_breeding_age_days:
            continue
        if _is_currently_pregnant(female):
            continue
        if _has_active_mating(female):
            continue
        last_child = (
            Animal.query.filter_by(mother_id=female.id)
            .order_by(Animal.birth_date.desc()).first()
        )
        if last_child and last_child.birth_date:
            rest_days = (today - last_child.birth_date).days
            if rest_days < fs.min_rest_after_birth_days:
                continue
        if Disease.query.filter_by(animal_id=female.id, status="active").count() > 0:
            continue
        result.append(female)
    return result


FILTERS = {
    "all": (_l("الكل"), lambda: _active_query().order_by(Animal.animal_no).all()),
    "lambs": (_l("البهم"), _lambs),
    "males": (_l("الذكور"), _males),
    "near_birth": (_l("قريب الولادة"), _near_birth),
    "mated": (_l("المقرعات"), _mated),
    "productive": (_l("دافع"), lambda: _productive_split()[0]),
    "unproductive": (_l("غير دافع"), lambda: _productive_split()[1]),
    "nursing": (_l("المرضعات"), _nursing),
    "fattening": (_l("التسمين"), _fattening),
    "dead": (_l("النفوق"), _dead),
    "ready_to_mate": (_l("جاهزة للتقريع"), _ready_to_mate),
    "ostrich": (_l("النعام"), _ostriches),
}


def get_filtered(filter_key: str):
    _, fn = FILTERS.get(filter_key, FILTERS["all"])
    return fn()


def get_counts() -> dict:
    return {key: len(fn()) for key, (_, fn) in FILTERS.items()}
