"""بند إضافي 111 — تذكير نهاية فترة سحب الدواء عند إغلاق مرض. قبل هذا
البند، `withdrawal_until` كان يُستخدم بس كبوابة منع بيع، بدون أي تذكير
فعلي ينبّهك لما تنتهي الفترة."""
from datetime import date, timedelta

from app.extensions import db
from app.models import Disease, Task
from factories import make_animal


def _make_disease(animal, withdrawal_until=None):
    d = Disease(animal_id=animal.id, disease_name="مرض اختبار", date=date.today(),
                status="active", withdrawal_until=withdrawal_until)
    db.session.add(d)
    db.session.commit()
    return d


def test_closing_disease_with_withdrawal_creates_reminder_task(app, logged_in_client):
    animal = make_animal(animal_no="WR-01")
    until = date.today() + timedelta(days=7)
    disease = _make_disease(animal, withdrawal_until=until)

    resp = logged_in_client.post(f"/health/diseases/{disease.id}/close", data={"recovery_note": "تعافى"})
    assert resp.status_code == 302

    task = Task.query.filter_by(task_type="withdrawal_reminder", animal_id=animal.id).first()
    assert task is not None
    assert task.due_date == until
    assert task.status == "suggested"
    assert animal.animal_no in task.title


def test_closing_disease_without_withdrawal_creates_no_task(app, logged_in_client):
    animal = make_animal(animal_no="WR-02")
    disease = _make_disease(animal, withdrawal_until=None)

    logged_in_client.post(f"/health/diseases/{disease.id}/close", data={"recovery_note": "تعافى"})

    task = Task.query.filter_by(task_type="withdrawal_reminder", animal_id=animal.id).first()
    assert task is None
