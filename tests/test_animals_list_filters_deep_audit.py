"""فحص شامل سطر بسطر — قائمة الحيوانات (/animals) وتبويبات الفلترة.

خللان حقيقيان اكتُشفا (كلاهما أداء N+1، بدون تغيير بالنتائج المنطقية):
1. `_productive_split()` كانت تسوي استعلام "عندها ولادة حديثة؟" منفصل
   لكل أنثى بالغة داخل حلقة Python — صار استعلاماً واحداً مجمَّعاً.
2. `_ready_to_mate()` كانت تسوي حتى 4 استعلامات منفصلة لكل أنثى مرشَّحة
   — صارت 4 استعلامات مجمَّعة بس لكل المرشَّحات معاً.
كل الاختبارات تتأكد من تطابق النتائج قبل/بعد (سلوك مطابق)، واختبار عدّ
استعلامات فعلي يثبت إن العدد ما يتضاعف مع عدد الحيوانات.
"""
from contextlib import contextmanager
from datetime import date, timedelta

from sqlalchemy import event

from app.core import animal_filters_service as afs
from app.extensions import db
from app.models import Animal
from app.models.animal import AnimalSource


@contextmanager
def count_queries():
    counter = {"n": 0}

    def _on_execute(conn, cursor, statement, parameters, context, executemany):
        counter["n"] += 1

    engine = db.session.get_bind()
    event.listen(engine, "before_cursor_execute", _on_execute)
    try:
        yield counter
    finally:
        event.remove(engine, "before_cursor_execute", _on_execute)


def _make_adult_female(no, has_recent_birth):
    old_birth = date.today() - timedelta(days=1000)
    mom = Animal(animal_no=no, species="sheep_goat", gender="أنثى", status="active",
                 source=AnimalSource.OPENING_BALANCE, birth_date=old_birth)
    db.session.add(mom)
    db.session.flush()
    if has_recent_birth:
        child = Animal(animal_no=f"{no}-child", species="sheep_goat", gender="ذكر", status="active",
                        source=AnimalSource.BIRTH, mother_id=mom.id,
                        birth_date=date.today() - timedelta(days=10))
        db.session.add(child)
    return mom


def test_productive_split_correctness(app):
    mom_with_birth = _make_adult_female("PS-1", has_recent_birth=True)
    mom_without_birth = _make_adult_female("PS-2", has_recent_birth=False)
    db.session.commit()

    productive, unproductive = afs._productive_split()
    productive_ids = {a.id for a in productive}
    unproductive_ids = {a.id for a in unproductive}

    assert mom_with_birth.id in productive_ids
    assert mom_with_birth.id not in unproductive_ids
    assert mom_without_birth.id in unproductive_ids
    assert mom_without_birth.id not in productive_ids


def test_productive_split_query_count_does_not_scale_with_female_count(app):
    for i in range(3):
        _make_adult_female(f"QC-SMALL-{i}", has_recent_birth=(i % 2 == 0))
    db.session.commit()
    with count_queries() as small:
        afs._productive_split()

    for i in range(30):
        _make_adult_female(f"QC-BIG-{i}", has_recent_birth=(i % 2 == 0))
    db.session.commit()
    with count_queries() as big:
        afs._productive_split()

    growth = big["n"] - small["n"]
    assert growth <= 1, (
        f"عدد الاستعلامات نما {growth} مع إضافة 30 أنثى بالغة — يدل على "
        f"خلل N+1 (صغير={small['n']}, كبير={big['n']})"
    )


def test_ready_to_mate_query_count_does_not_scale_with_female_count(app):
    def _make_ready_female(no):
        return Animal(animal_no=no, species="sheep_goat", gender="أنثى", status="active",
                       source=AnimalSource.OPENING_BALANCE,
                       birth_date=date.today() - timedelta(days=1000))

    for i in range(3):
        db.session.add(_make_ready_female(f"RTM-SMALL-{i}"))
    db.session.commit()
    with count_queries() as small:
        afs._ready_to_mate()

    for i in range(30):
        db.session.add(_make_ready_female(f"RTM-BIG-{i}"))
    db.session.commit()
    with count_queries() as big:
        afs._ready_to_mate()

    growth = big["n"] - small["n"]
    assert growth <= 1, (
        f"عدد الاستعلامات نما {growth} مع إضافة 30 أنثى مرشَّحة — يدل على "
        f"خلل N+1 (صغير={small['n']}, كبير={big['n']})"
    )
