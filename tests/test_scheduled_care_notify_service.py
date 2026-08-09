"""بند إضافي 163 (المرحلة د-2) — تأكيد إن مهام التطعيم/الوزن المتأخر
المتولّدة حديثاً تحاول ترسل إشعار تيليجرام فعلياً (مع mock)."""
from datetime import date, timedelta
from unittest.mock import patch

from app.extensions import db
from app.core import scheduled_care_service
from app.models import Vaccination
from factories import make_animal


def test_new_vaccination_due_task_notifies_via_telegram(app, owner):
    owner.telegram_chat_id = "1010"
    db.session.commit()

    animal = make_animal(animal_no="NTF-01")
    db.session.add(Vaccination(
        animal_id=animal.id, vaccine_name="لقاح تجريبي",
        date=date.today() - timedelta(days=60),
        next_due_date=date.today() - timedelta(days=5),
    ))
    db.session.commit()

    with patch("app.core.telegram_service.notify_user") as mock_notify:
        created = scheduled_care_service.generate_vaccination_due_tasks()
    assert len(created) == 1
    mock_notify.assert_called_once()
    assert created[0].title in mock_notify.call_args[0][1]


def test_idempotent_rerun_does_not_notify_again(app, owner):
    owner.telegram_chat_id = "1011"
    db.session.commit()

    animal = make_animal(animal_no="NTF-02")
    db.session.add(Vaccination(
        animal_id=animal.id, vaccine_name="لقاح تجريبي",
        date=date.today() - timedelta(days=60),
        next_due_date=date.today() - timedelta(days=5),
    ))
    db.session.commit()

    scheduled_care_service.generate_vaccination_due_tasks()
    with patch("app.core.telegram_service.notify_user") as mock_notify:
        second = scheduled_care_service.generate_vaccination_due_tasks()
    assert second == []
    mock_notify.assert_not_called()
