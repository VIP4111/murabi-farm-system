"""اختبارات تتبّع تنفيذ العامل بدقة (بند إضافي 54 — كان موثّقاً كفجوة
بند 27.11): مين باشر التنفيذ، مدة الإنجاز الفعلية، وتسجيل تعذّر المهمة
بسبب من قائمة مقفلة بدل ما تختفي المهمة بصمت."""
from datetime import datetime, timedelta, timezone

import pytest

from app.extensions import db
from app.team import task_service as tsvc
from factories import make_animal, make_barn


def _assign(owner, worker, **kwargs):
    return tsvc.assign_task(actor=owner, title="مهمة اختبار", assignee_id=worker.id, **kwargs)


def test_start_task_records_accepted_by_and_server_time_source(app, owner, worker):
    task = _assign(owner, worker)
    tsvc.start_task(task, actor=worker)
    assert task.accepted_by_id == worker.id
    assert task.server_time_source == "server"
    assert task.started_at is not None


def test_complete_task_computes_duration_minutes(app, owner, worker):
    task = _assign(owner, worker)
    tsvc.start_task(task, actor=worker)
    # نرجع started_at 15 دقيقة للخلف عشان نتحقق من حساب المدة الفعلي
    task.started_at = datetime.now(timezone.utc) - timedelta(minutes=15)
    db.session.commit()

    tsvc.complete_task(task, actor=worker, note="تم بنجاح")
    assert task.status == "done"
    assert task.duration_minutes is not None
    assert 14 <= task.duration_minutes <= 16


def test_complete_task_saves_voice_note_url(app, owner, worker):
    task = _assign(owner, worker)
    tsvc.start_task(task, actor=worker)
    tsvc.complete_task(task, actor=worker, voice_note_url="/static/uploads/audio/x.webm")
    assert task.voice_note_url == "/static/uploads/audio/x.webm"


def test_fail_task_records_reason_and_status(app, owner, worker):
    task = _assign(owner, worker)
    tsvc.start_task(task, actor=worker)
    tsvc.fail_task(task, actor=worker, reason="نقص الأدوات", note="ما فيه شيء بالمخزن")
    assert task.status == "failed"
    assert task.failure_reason == "نقص الأدوات"
    assert task.failed_at is not None
    assert task.completion_note == "ما فيه شيء بالمخزن"


def test_fail_task_rejects_unknown_reason(app, owner, worker):
    task = _assign(owner, worker)
    tsvc.start_task(task, actor=worker)
    with pytest.raises(tsvc.TaskStateError):
        tsvc.fail_task(task, actor=worker, reason="سبب غير موجود بالقائمة")


def test_fail_task_rejects_wrong_assignee(app, owner, worker):
    task = _assign(owner, worker)
    tsvc.start_task(task, actor=worker)
    with pytest.raises(tsvc.TaskPermissionError):
        tsvc.fail_task(task, actor=owner, reason="نقص الأدوات")


def test_fail_task_respects_dependency_lock(app, owner, worker):
    first = _assign(owner, worker)
    second = _assign(owner, worker, depends_on_task_id=first.id)
    tsvc.start_task(first, actor=worker)
    # المهمة الثانية مقفلة لين تكمل الأولى — حتى تسجيل التعذّر ممنوع
    with pytest.raises(tsvc.TaskStateError):
        tsvc.fail_task(second, actor=worker, reason="نقص الأدوات")
