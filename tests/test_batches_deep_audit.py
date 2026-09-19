"""فحص شامل سطر بسطر — ميزة الدفعات.

أخطر خلل: زر "إلحاق بمرحلة الدفعة" كان يظهر لأي رأس نشطة غير مستبعدة،
حتى لو تقدّمت أصلاً مع بقية الدفعة بالتقدّم الجماعي — ضغطه مرة ثانية
يولّد مهمة مكرَّرة (وبمرحلة التوزيع يعيد كتابة الحظيرة بصمت). بالإضافة
لخلل تحطّم (وزن/سعر أو رقم حظيرة غير صالح يسقط بخطأ 500) وN+1 بشاشتي
القائمة والتفاصيل."""
from contextlib import contextmanager
from datetime import date

import pytest

from app.core import batch_service
from app.extensions import db
from app.models import AnimalBatch, Task
from factories import make_barn


@contextmanager
def count_queries():
    counter = {"n": 0}

    def _on_execute(conn, cursor, statement, parameters, context, executemany):
        counter["n"] += 1

    engine = db.session.get_bind()
    event_module = __import__("sqlalchemy").event
    event_module.listen(engine, "before_cursor_execute", _on_execute)
    try:
        yield counter
    finally:
        event_module.remove(engine, "before_cursor_execute", _on_execute)


def _entries(n=3, prefix="BQ"):
    return [{"animal_no": f"{prefix}-{i}", "gender": "أنثى", "color": "أبيض"} for i in range(1, n + 1)]


def test_catch_up_after_bulk_advance_is_rejected_not_duplicated(app):
    """رأس تقدّمت أصلاً بالتقدّم الجماعي (مرحلة 1→2) — ضغط "إلحاق"
    عليها بعدين لازم يُرفض، مو يولّد مهمة ترقيم ثانية."""
    make_barn(barn_no="ISO-BQ", barn_type="عزل")
    batch = batch_service.create_batch(
        source="purchase", arrival_date=date.today(), notes=None,
        actor_user_id=1, entries=_entries(2),
    )
    batch_service.advance_batch_stage(batch, actor_user_id=1)
    animal = batch.animals[0]

    tasks_before = Task.query.filter_by(source_type="AnimalBatch", source_id=batch.id,
                                         task_type="batch_tagging_check", animal_id=animal.id).count()
    assert tasks_before == 1

    with pytest.raises(ValueError):
        batch_service.advance_single_animal(batch, animal, actor_user_id=1)

    tasks_after = Task.query.filter_by(source_type="AnimalBatch", source_id=batch.id,
                                        task_type="batch_tagging_check", animal_id=animal.id).count()
    assert tasks_after == 1, "ضغطة إلحاق ثانية على رأس تقدّمت أصلاً ما يفترض تولّد مهمة مكرَّرة"


def test_catch_up_still_works_for_a_genuinely_held_animal(app):
    """رأس مستبعدة فردياً (لم تتقدّم مع الدفعة) — بعد تحرير الاستبعاد،
    الإلحاق يفترض يشتغل عادي ويولّد مهمتها الأولى (مو مكرَّرة)."""
    make_barn(barn_no="ISO-BQ2", barn_type="عزل")
    batch = batch_service.create_batch(
        source="purchase", arrival_date=date.today(), notes=None,
        actor_user_id=1, entries=_entries(2, prefix="BQ2"),
    )
    suspect = batch.animals[0]
    batch_service.hold_animal(suspect, reason="اشتباه مرض", actor_user_id=1)
    batch_service.advance_batch_stage(batch, actor_user_id=1)  # يتقدّم بس غير المستبعد
    batch_service.release_hold(suspect, actor_user_id=1)

    task = batch_service.advance_single_animal(batch, suspect, actor_user_id=1)
    assert task is not None
    count = Task.query.filter_by(source_type="AnimalBatch", source_id=batch.id,
                                  task_type="batch_tagging_check", animal_id=suspect.id).count()
    assert count == 1


def test_batches_new_rejects_invalid_weight_with_flash_not_crash(logged_in_client):
    resp = logged_in_client.post("/batches/new", data={
        "source": "purchase", "arrival_date": date.today().isoformat(),
        "gender_0": "أنثى", "weight_0": "not-a-number",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert AnimalBatch.query.count() == 0


def test_batches_list_query_count_does_not_scale_with_batch_count(logged_in_client):
    make_barn(barn_no="ISO-QC", barn_type="عزل")

    def _make_batches(n, start, prefix):
        for i in range(start, start + n):
            batch_service.create_batch(source="purchase", arrival_date=date.today(), notes=None,
                                        actor_user_id=1, entries=_entries(2, prefix=f"{prefix}{i}"))

    _make_batches(2, 0, "QCS")
    with count_queries() as small:
        logged_in_client.get("/batches/")

    _make_batches(10, 0, "QCB")
    with count_queries() as big:
        logged_in_client.get("/batches/")

    growth = big["n"] - small["n"]
    assert growth <= 3, (
        f"عدد الاستعلامات نما {growth} مع إضافة 10 دفعات — يدل على خلل "
        f"N+1 (صغير={small['n']}, كبير={big['n']})"
    )
