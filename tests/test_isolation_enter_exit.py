"""بند إضافي 148 — طلبك: "احتاج زر واضح عزل / خروج من العزل... لو
قلت عزل يعطيني النظام خيارات علشان اسجل سبب العزل وذا بطلعه قبل وقته
يعطيني خيارات الزامية مثل هل تم تحصينه... اسماح بنقل من عزل مثل حظيرة
رقم٤ لحظيرة رقم٣ بدون ما تتاثر المعلومات الي ماشي عليها النظام مثل
وصل لليوم رقم ١٤ يكمل العد وكيذا"."""
from datetime import date, timedelta

import pytest

from app.core import isolation_service
from app.models import FarmSettings
from factories import make_animal, make_barn


def test_enter_isolation_sets_barn_and_start_date(app):
    iso = make_barn(barn_no="ISO-A", barn_type="عزل")
    animal = make_animal(animal_no="ISOE-01")
    isolation_service.enter_isolation(
        animal_id=animal.id, reason="اشتباه مرض", note_date=date.today(),
        actor_user_id=1, barn_id=iso.id,
    )
    assert animal.barn_id == iso.id
    assert animal.isolation_started_at == date.today()


def test_moving_between_isolation_barns_does_not_reset_day_counter(app):
    """طلبك تحديداً: نقل من حظيرة عزل لحظيرة عزل ثانية ما يأثر على عداد
    الأيام — يوم 14 يكمل العد، ما يرجع للصفر."""
    iso1 = make_barn(barn_no="ISO-B1", barn_type="عزل")
    iso2 = make_barn(barn_no="ISO-B2", barn_type="عزل")
    animal = make_animal(animal_no="ISOE-02")
    start = date.today() - timedelta(days=14)

    isolation_service.enter_isolation(
        animal_id=animal.id, reason="دخول أول", note_date=start,
        actor_user_id=1, barn_id=iso1.id,
    )
    assert animal.isolation_started_at == start

    # نقل بين حظيرتي عزل — "دخول عزل" ثانية ما يصفّر التاريخ لأنه idempotent
    isolation_service.enter_isolation(
        animal_id=animal.id, reason=None, note_date=date.today(),
        actor_user_id=1, barn_id=iso2.id,
    )
    assert animal.barn_id == iso2.id
    assert animal.isolation_started_at == start  # لسا نفس تاريخ الدخول الأول


def test_exit_isolation_after_minimum_days_succeeds_without_conditions(app):
    normal_barn = make_barn(barn_no="NRM-01", barn_type="عادية")
    animal = make_animal(animal_no="ISOE-03")
    fs = FarmSettings.get()
    start = date.today() - timedelta(days=fs.isolation_days + 1)
    animal.isolation_started_at = start

    isolation_service.exit_isolation(
        animal_id=animal.id, target_barn_id=normal_barn.id,
        note_date=date.today(), actor_user_id=1,
    )
    assert animal.barn_id == normal_barn.id
    assert animal.isolation_started_at is None


def test_exit_isolation_early_without_confirmations_is_blocked(app):
    normal_barn = make_barn(barn_no="NRM-02", barn_type="عادية")
    animal = make_animal(animal_no="ISOE-04")
    animal.isolation_started_at = date.today() - timedelta(days=1)

    with pytest.raises(isolation_service.IsolationExitBlocked):
        isolation_service.exit_isolation(
            animal_id=animal.id, target_barn_id=normal_barn.id,
            note_date=date.today(), actor_user_id=1,
        )
    assert animal.isolation_started_at is not None  # ما خرج


def test_exit_isolation_early_with_both_confirmations_succeeds(app):
    normal_barn = make_barn(barn_no="NRM-03", barn_type="عادية")
    animal = make_animal(animal_no="ISOE-05")
    animal.isolation_started_at = date.today() - timedelta(days=1)

    isolation_service.exit_isolation(
        animal_id=animal.id, target_barn_id=normal_barn.id,
        note_date=date.today(), actor_user_id=1,
        vet_checked=True, vaccinated=True,
    )
    assert animal.barn_id == normal_barn.id
    assert animal.isolation_started_at is None


def test_isolation_enter_route_shows_button_and_form(logged_in_client):
    make_barn(barn_no="ISO-R1", barn_type="عزل")
    animal = make_animal(animal_no="ISOR-01")
    detail_resp = logged_in_client.get(f"/animals/{animal.id}")
    assert "دخول عزل" in detail_resp.get_data(as_text=True)

    form_resp = logged_in_client.get(f"/animals/{animal.id}/isolation/enter")
    assert form_resp.status_code == 200
    assert "سبب العزل" in form_resp.get_data(as_text=True)


def test_isolation_exit_route_flashes_error_when_blocked(logged_in_client):
    normal_barn = make_barn(barn_no="NRM-04", barn_type="عادية")
    animal = make_animal(animal_no="ISOR-02")
    animal.isolation_started_at = date.today()

    resp = logged_in_client.post(f"/animals/{animal.id}/isolation/exit", data={
        "date": date.today().isoformat(), "barn_id": str(normal_barn.id),
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "خروج مبكر" in resp.get_data(as_text=True)
