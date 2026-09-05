"""استكمال تدقيق الأداء (بلاغ: "ضعف في التصفح غير سريع") — لقينا نفس
نمط N+1 بـ`alerts_service._weight_schedule_missing_reference_date()`:
كان يسوي استعلام AnimalWeight منفصل *لكل رأس نشط بالمزرعة على حدة* —
تُستدعى هذي الدالة بكل زيارة للرئيسية وشاشة التنبيهات. الإصلاح: استعلام
واحد يجيب كل animal_id عنده وزن مسجَّل، ونفلتر بالذاكرة."""
from datetime import date

from sqlalchemy import event

from app.extensions import db
from app.core.alerts_service import _weight_schedule_missing_reference_date
from app.models import AnimalWeight
from app.models.animal import AnimalSource
from tests.factories import make_animal


def _count_select_queries(fn):
    queries = []

    def _listener(conn, cursor, statement, parameters, context, executemany):
        if statement.strip().upper().startswith("SELECT"):
            queries.append(statement)

    event.listen(db.engine, "before_cursor_execute", _listener)
    try:
        return fn(), queries
    finally:
        event.remove(db.engine, "before_cursor_execute", _listener)


def test_query_count_does_not_scale_with_animal_count(app):
    with app.app_context():
        for i in range(20):
            make_animal(animal_no=f"TIP-WM-{i}", gender="أنثى", source=AnimalSource.GIFT)

        result, queries = _count_select_queries(_weight_schedule_missing_reference_date)
        # ما نتأكد من محتوى النتيجة (كل الرؤوس هنا بدون تاريخ ولادة/شراء/
        # دخول أصلاً حسب make_animal الافتراضي، فهي متوقَّعة تظهر بالتنبيه)
        # — نتأكد بس إن عدد الاستعلامات ثابت (2-3) بغض النظر عن عدد
        # الرؤوس، مو استعلام لكل رأس (كان قبل الإصلاح 20+ استعلام هنا).
        assert len(queries) <= 4, f"عدد استعلامات كبير ({len(queries)}) لـ20 رأس — احتمال N+1"


def test_animal_with_weight_record_is_excluded_from_missing_count(app):
    with app.app_context():
        with_weight = make_animal(animal_no="TIP-WM-HASWEIGHT", gender="أنثى", source=AnimalSource.GIFT)
        db.session.add(AnimalWeight(animal_id=with_weight.id, date=date.today(), weight=40))
        make_animal(animal_no="TIP-WM-NOWEIGHT", gender="أنثى", source=AnimalSource.GIFT)
        db.session.commit()

        alerts = _weight_schedule_missing_reference_date()
        assert len(alerts) == 1
        assert "1 رأس" in alerts[0]["label"]
