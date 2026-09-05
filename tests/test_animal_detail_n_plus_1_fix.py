"""بلاغ مستخدم: "اذا ضغطت على رقم حيوان بطيء وهو يعرض بيانات الحيوان".
السبب: `animal_profile_service.get_profile()` يبني تسلسل زمني يوصل
لعلاقات (`VetVisit.doctor`, `AnimalNote.created_by`,
`Mating.male`/`Mating.female`) داخل حلقة for بدون تحميل مسبق — كل صف
كان يسوي استعلام قاعدة بيانات منفصل له وحده (N+1 كلاسيكي). لرأس عنده
تاريخ طويل هذا يعني عشرات الاستعلامات الزايدة بكل فتحة صفحة، فوق قاعدة
بيانات بعيدة (Neon) كل استعلام له زمن شبكة حقيقي. الإصلاح: joinedload
على الثلاث علاقات."""
from datetime import date

from sqlalchemy import event

from app.extensions import db
from app.core.animal_profile_service import get_profile
from app.models import Doctor, VetVisit, AnimalNote, User, Role
from app.models.repro import Mating
from tests.factories import make_animal


def _count_queries(fn):
    queries = []

    def _listener(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    event.listen(db.engine, "before_cursor_execute", _listener)
    try:
        fn()
    finally:
        event.remove(db.engine, "before_cursor_execute", _listener)
    return queries


def _make_history(subject_no, row_count):
    # كل صف له طبيب/مبلّغ/فحل *مختلف* عمداً — لو كلهم نفس الكائن،
    # SQLAlchemy identity map يخزّن أول استعلام ويعيد استخدامه للصفوف
    # الباقية حتى بدون joinedload، فيخفي مشكلة N+1 الحقيقية بدل ما
    # يكشفها (بيانات مزرعة حقيقية غالباً متنوّعة: أطباء وعمال مختلفين).
    role = Role.query.filter_by(name="worker").first()
    subject = make_animal(animal_no=subject_no, gender="أنثى")
    db.session.flush()

    for i in range(row_count):
        doctor = Doctor(name=f"د. {subject_no}-{i}")
        reporter = User(name=f"عامل {subject_no}-{i}", phone=f"05{abs(hash((subject_no, i))) % 100000000:08d}", role_id=role.id)
        reporter.set_password("pass1234")
        male = make_animal(animal_no=f"{subject_no}-M-{i}", gender="ذكر")
        db.session.add(doctor)
        db.session.add(reporter)
        db.session.flush()
        db.session.add(VetVisit(animal_id=subject.id, doctor_id=doctor.id, date=date.today()))
        db.session.add(AnimalNote(animal_id=subject.id, date=date.today(), note=f"ملاحظة {i}", created_by_id=reporter.id))
        db.session.add(Mating(female_id=subject.id, male_id=male.id, date=date.today()))
    db.session.commit()
    return subject


def test_animal_detail_query_count_does_not_scale_with_row_count(app):
    """قبل الإصلاح: كل صف إضافي (زيارة/ملاحظة/تقريع) يضيف استعلام علاقة
    منفصل له وحده (N+1) — عدد الاستعلامات يكبر خطياً مع عدد الصفوف.
    بعد joinedload، عدد الاستعلامات شبه ثابت بغض النظر عن عدد الصفوف —
    الفرق بين رأس عنده صفين وآخر عنده 10 لازم يكون قريب من صفر، مو
    متناسب مع فرق عدد الصفوف (24 صف إضافي زيادة)."""
    with app.app_context():
        small_subject = _make_history("TIP-NP1-SMALL", row_count=2)
        big_subject = _make_history("TIP-NP1-BIG", row_count=10)

        small_queries = _count_queries(lambda: get_profile(small_subject))
        big_queries = _count_queries(lambda: get_profile(big_subject))
        small_count = sum(1 for q in small_queries if q.strip().upper().startswith("SELECT"))
        big_count = sum(1 for q in big_queries if q.strip().upper().startswith("SELECT"))

        growth = big_count - small_count
        assert growth <= 2, (
            f"عدد الاستعلامات كبر مع عدد الصفوف ({small_count} → {big_count}, "
            f"فرق {growth}) — احتمال N+1 رجع بدل ما يكون ثابت بـjoinedload"
        )
