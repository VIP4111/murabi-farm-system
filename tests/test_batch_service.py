"""اختبارات مسار استقبال دفعة جديدة بمراحل (بند إضافي 52، جزء 2) —
حجر → ترقيم/فحص → توزيع، مع تقدّم جماعي بضغطة زر وإمكانية استبعاد
رأس مشتبه بها فردياً من التقدّم الجماعي (سيناريوك الصريح)."""
from datetime import date

import pytest

from app.core import batch_service
from app.extensions import db
from app.models import AnimalBatch, Task
from factories import make_barn


def _entries(n=3, prefix="B1"):
    return [{"animal_no": f"{prefix}-{i}", "gender": "أنثى", "color": "أبيض"} for i in range(1, n + 1)]


def test_create_batch_registers_animals_and_isolates_and_creates_tasks(app):
    make_barn(barn_no="ISO", barn_type="عزل")
    batch = batch_service.create_batch(
        source="purchase", arrival_date=date.today(), notes=None,
        actor_user_id=1, entries=_entries(3),
    )
    assert batch.stage == AnimalBatch.STAGE_QUARANTINE
    assert len(batch.animals) == 3
    for a in batch.animals:
        assert a.barn.barn_type == "عزل"
    tasks = Task.query.filter_by(source_type="AnimalBatch", source_id=batch.id).all()
    task_types = {t.task_type for t in tasks}
    assert task_types == {"batch_spray", "batch_initial_vaccination"}
    assert len(tasks) == 6  # 2 مهام × 3 رؤوس


def test_create_batch_requires_at_least_one_entry(app):
    with pytest.raises(ValueError):
        batch_service.create_batch(source="purchase", arrival_date=date.today(), notes=None,
                                    actor_user_id=1, entries=[])


def test_advance_batch_stage_bulk_advances_all_and_skips_held(app):
    make_barn(barn_no="ISO2", barn_type="عزل")
    batch = batch_service.create_batch(
        source="purchase", arrival_date=date.today(), notes=None,
        actor_user_id=1, entries=_entries(3, prefix="B2"),
    )
    suspect = batch.animals[0]
    batch_service.hold_animal(suspect, reason="اشتباه مرض", actor_user_id=1)

    created = batch_service.advance_batch_stage(batch, actor_user_id=1)

    assert batch.stage == AnimalBatch.STAGE_TAGGING
    assert len(created) == 2  # استُثنيت المشتبه بها
    tagging_animal_ids = {t.animal_id for t in created}
    assert suspect.id not in tagging_animal_ids


def test_advance_batch_stage_rejects_wrong_stage(app):
    make_barn(barn_no="ISO3", barn_type="عزل")
    batch = batch_service.create_batch(
        source="gift", arrival_date=date.today(), notes=None,
        actor_user_id=1, entries=_entries(1, prefix="B3"),
    )
    batch_service.advance_batch_stage(batch, actor_user_id=1)
    with pytest.raises(ValueError):
        batch_service.advance_batch_stage(batch, actor_user_id=1)


def test_distribute_batch_moves_animals_to_assigned_permanent_barns(app):
    make_barn(barn_no="ISO4", barn_type="عزل")
    permanent = make_barn(barn_no="PERM-1", barn_type="عادية")
    batch = batch_service.create_batch(
        source="purchase", arrival_date=date.today(), notes=None,
        actor_user_id=1, entries=_entries(2, prefix="B4"),
    )
    batch_service.advance_batch_stage(batch, actor_user_id=1)

    assignments = {a.id: permanent.id for a in batch.animals}
    created = batch_service.distribute_batch(batch, assignments=assignments, actor_user_id=1)

    assert batch.stage == AnimalBatch.STAGE_DISTRIBUTED
    assert len(created) == 2
    for a in batch.animals:
        assert a.barn_id == permanent.id


def test_hold_and_release_animal(app):
    make_barn(barn_no="ISO5", barn_type="عزل")
    batch = batch_service.create_batch(
        source="purchase", arrival_date=date.today(), notes=None,
        actor_user_id=1, entries=_entries(1, prefix="B5"),
    )
    animal = batch.animals[0]
    batch_service.hold_animal(animal, reason="اشتباه", actor_user_id=1)
    assert animal.batch_hold_reason == "اشتباه"

    batch_service.release_hold(animal, actor_user_id=1)
    assert animal.batch_hold_reason is None


def test_hold_animal_requires_reason(app):
    make_barn(barn_no="ISO6", barn_type="عزل")
    batch = batch_service.create_batch(
        source="purchase", arrival_date=date.today(), notes=None,
        actor_user_id=1, entries=_entries(1, prefix="B6"),
    )
    with pytest.raises(ValueError):
        batch_service.hold_animal(batch.animals[0], reason="", actor_user_id=1)


def test_advance_single_animal_catches_up_released_animal(app):
    """السيناريو المطلوب صراحة: رأس مشتبه بها تُستبعد وتبقى خلف بينما
    بقية الدفعة تتقدّم جماعياً — لما تُحرَّر لاحقاً، تلحق فردياً بمرحلة
    الدفعة الحالية بدون التأثير على بقية الدفعة."""
    make_barn(barn_no="ISO7", barn_type="عزل")
    permanent = make_barn(barn_no="PERM-2", barn_type="عادية")
    batch = batch_service.create_batch(
        source="purchase", arrival_date=date.today(), notes=None,
        actor_user_id=1, entries=_entries(2, prefix="B7"),
    )
    suspect, healthy = batch.animals[0], batch.animals[1]
    batch_service.hold_animal(suspect, reason="اشتباه", actor_user_id=1)
    batch_service.advance_batch_stage(batch, actor_user_id=1)
    batch_service.distribute_batch(batch, assignments={healthy.id: permanent.id}, actor_user_id=1)

    assert batch.stage == AnimalBatch.STAGE_DISTRIBUTED
    assert suspect.barn_id != permanent.id  # لسا خلف

    batch_service.release_hold(suspect, actor_user_id=1)
    with pytest.raises(ValueError):
        batch_service.advance_single_animal(batch, suspect, actor_user_id=1)  # ناقصة barn_id
    task = batch_service.advance_single_animal(batch, suspect, actor_user_id=1, barn_id=permanent.id)

    assert suspect.barn_id == permanent.id
    assert task.task_type == "batch_feed_link"


def test_advance_single_animal_rejects_while_still_held(app):
    make_barn(barn_no="ISO8", barn_type="عزل")
    batch = batch_service.create_batch(
        source="purchase", arrival_date=date.today(), notes=None,
        actor_user_id=1, entries=_entries(1, prefix="B8"),
    )
    animal = batch.animals[0]
    batch_service.hold_animal(animal, reason="اشتباه", actor_user_id=1)
    with pytest.raises(ValueError):
        batch_service.advance_single_animal(batch, animal, actor_user_id=1)
