"""اختبارات تقييد العامل الميداني بحظائره (بند إضافي 46، القسم ٥) —
app/team/routes._scoped_barn_ids و_validate_scoped_report."""
from flask_login import login_user

from app.team.routes import _scoped_barn_ids, _validate_scoped_report
from factories import make_animal, make_barn


def test_owner_is_unrestricted(app, owner):
    with app.test_request_context():
        login_user(owner)
        assert _scoped_barn_ids() is None


def test_worker_without_animals_view_is_scoped_to_assigned_barns(app, worker):
    barn = make_barn(barn_no="W-BARN", responsible_worker_id=worker.id)
    with app.test_request_context():
        login_user(worker)
        assert _scoped_barn_ids() == [barn.id]


def test_worker_with_no_assigned_barn_gets_empty_scope(app, worker):
    with app.test_request_context():
        login_user(worker)
        assert _scoped_barn_ids() == []


def test_validate_rejects_animal_outside_scope(app, worker):
    barn = make_barn(barn_no="W-BARN2", responsible_worker_id=worker.id)
    other_barn = make_barn(barn_no="OTHER")
    outside_animal = make_animal(animal_no="OUT-01", barn_id=other_barn.id)
    with app.test_request_context():
        login_user(worker)
        scope = _scoped_barn_ids()
        error = _validate_scoped_report(scope, outside_animal.id, None)
        assert error is not None and "خارج نطاق" in error


def test_validate_allows_animal_inside_scope(app, worker):
    barn = make_barn(barn_no="W-BARN3", responsible_worker_id=worker.id)
    inside_animal = make_animal(animal_no="IN-01", barn_id=barn.id)
    with app.test_request_context():
        login_user(worker)
        scope = _scoped_barn_ids()
        assert _validate_scoped_report(scope, inside_animal.id, None) is None


def test_validate_rejects_barn_outside_scope(app, worker):
    make_barn(barn_no="W-BARN4", responsible_worker_id=worker.id)
    other_barn = make_barn(barn_no="OTHER2")
    with app.test_request_context():
        login_user(worker)
        scope = _scoped_barn_ids()
        error = _validate_scoped_report(scope, None, other_barn.id)
        assert error is not None


def test_validate_is_noop_when_user_unrestricted(app, owner):
    other_barn = make_barn(barn_no="ANY")
    animal = make_animal(animal_no="ANY-01", barn_id=other_barn.id)
    with app.test_request_context():
        login_user(owner)
        scope = _scoped_barn_ids()
        assert _validate_scoped_report(scope, animal.id, None) is None
