"""استكمال تدقيق الأداء (بلاغ: "ضعف في التصفح غير سريع") — لقينا نفس
نمط N+1 بـ`break_even_summary()`: كان يسوي ٦+ استعلامات منفصلة *لكل
رأس نشط على حدة* (Finance، زيارات بيطرية، أمراض، تحصينات، خطة علف،
مبيعات مشابهة) — لمزرعة عندها رؤوس كثيرة يعني مئات الاستعلامات لفتحة
تقرير "التحليل المالي ونقطة التعادل" وحدة. الإصلاح: كل شي يُجاب مرة
وحدة قبل الحلقة ويُجمَّع بالذاكرة."""
from datetime import date

from sqlalchemy import event

from app.extensions import db
from app.core.animal_profile_service import break_even_summary
from app.models import VetVisit, Disease, Vaccination
from tests.factories import make_animal


def _count_select_queries(fn):
    queries = []

    def _listener(conn, cursor, statement, parameters, context, executemany):
        if statement.strip().upper().startswith("SELECT"):
            queries.append(statement)

    event.listen(db.engine, "before_cursor_execute", _listener)
    try:
        fn()
    finally:
        event.remove(db.engine, "before_cursor_execute", _listener)
    return len(queries)


def test_break_even_summary_query_count_does_not_scale_with_animal_count(app):
    with app.app_context():
        from app.models import Doctor
        doctor = Doctor(name="د. اختبار الأداء")
        db.session.add(doctor)
        db.session.flush()

        def make_batch(prefix, n):
            for i in range(n):
                a = make_animal(animal_no=f"{prefix}-{i}", gender="أنثى", price=100)
                db.session.add(VetVisit(animal_id=a.id, doctor_id=doctor.id, date=date.today(), cost=10))
                db.session.add(Disease(animal_id=a.id, disease_name="مرض", date=date.today(), status="closed", treatment_cost=5))
                db.session.add(Vaccination(animal_id=a.id, vaccine_name="لقاح", date=date.today(), cost=3))
            db.session.commit()

        make_batch("TIP-BE-SMALL", 3)
        small_count = _count_select_queries(break_even_summary)

        make_batch("TIP-BE-BIG", 15)
        big_count = _count_select_queries(break_even_summary)

        # لو رجع نمط N+1، عدد الاستعلامات يكبر بشكل متناسب مع عدد
        # الرؤوس الإضافية (18 رأس إضافي هنا). نتأكد إن الفرق صغير وثابت
        # تقريباً، مو متناسب مع عدد الرؤوس.
        assert big_count - small_count < 10, (
            f"عدد استعلامات break_even_summary كبر مع عدد الرؤوس "
            f"({small_count} → {big_count}) — احتمال N+1 رجع"
        )
