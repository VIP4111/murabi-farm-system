"""اختبارات حفظ مواعيد وجبات العلف من نموذج الحظيرة (بند إضافي 131) —
استبدال كامل بسيط عند كل حفظ، نفس فلسفة `_save_dose_rules`."""
from datetime import time

from app.extensions import db
from app.models import Barn, BarnFeedingSchedule
from factories import make_barn


def test_barns_new_saves_meal_times(logged_in_client, app):
    resp = logged_in_client.post("/barns/new", data={
        "barn_no": "MT-01", "barn_name": "حظيرة الاختبار",
        "meal_time": ["07:00", "13:00"],
    }, follow_redirects=True)
    assert resp.status_code == 200
    barn = Barn.query.filter_by(barn_no="MT-01").first()
    assert barn is not None
    times = sorted(s.meal_time.strftime("%H:%M") for s in barn.feeding_schedules)
    assert times == ["07:00", "13:00"]


def test_barns_edit_replaces_meal_times(logged_in_client, app):
    barn = make_barn(barn_no="MT-02")
    db.session.add(BarnFeedingSchedule(barn_id=barn.id, meal_time=time(6, 0)))
    db.session.commit()

    resp = logged_in_client.post(f"/barns/{barn.id}/edit", data={
        "barn_no": "MT-02", "barn_name": barn.barn_name,
        "meal_time": ["09:30"],
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(barn)
    times = [s.meal_time.strftime("%H:%M") for s in barn.feeding_schedules]
    assert times == ["09:30"]


def test_empty_meal_time_rows_ignored(logged_in_client, app):
    resp = logged_in_client.post("/barns/new", data={
        "barn_no": "MT-03", "barn_name": "حظيرة بدون مواعيد",
        "meal_time": ["", ""],
    }, follow_redirects=True)
    assert resp.status_code == 200
    barn = Barn.query.filter_by(barn_no="MT-03").first()
    assert barn.feeding_schedules == []
