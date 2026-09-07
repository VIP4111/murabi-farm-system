"""فحص عميق — قسم الأعلاف: `barn_plans_new` كانت تحفظ `daily_qty_per_
animal_kg` مباشرة بدون أي تحقق — قيمة سالبة أو صفرية تنكسر بها تكلفة
الرأس اليومية المحسوبة منها مباشرة (`current_barn_daily_cost_per_head`)
وتقارير التكلفة الشهرية اللي تعتمد عليها. وتاريخ نهاية أقدم من تاريخ
البداية كان يمر بصمت أيضاً."""
from datetime import date

from app.extensions import db
from app.models import FeedBarnPlan, FeedRation
from tests.factories import make_barn


def _make_ration():
    ration = FeedRation(name="وصفة اختبار", purpose="صيانة")
    db.session.add(ration)
    db.session.commit()
    return ration


def test_negative_daily_qty_rejected_and_saves_nothing(app, logged_in_client):
    barn = make_barn(barn_no="TIP-PLAN-1")
    ration = _make_ration()

    resp = logged_in_client.post("/feed/barn-plans/new", data={
        "barn_id": str(barn.id), "ration_id": str(ration.id),
        "daily_qty_per_animal_kg": "-2.5", "start_date": date.today().isoformat(),
    }, follow_redirects=True)
    assert resp.status_code == 200

    assert FeedBarnPlan.query.filter_by(barn_id=barn.id).count() == 0, \
        "خطة تغذية بكمية سالبة انحفظت رغم إنها غير منطقية"


def test_zero_daily_qty_rejected(app, logged_in_client):
    barn = make_barn(barn_no="TIP-PLAN-2")
    ration = _make_ration()

    resp = logged_in_client.post("/feed/barn-plans/new", data={
        "barn_id": str(barn.id), "ration_id": str(ration.id),
        "daily_qty_per_animal_kg": "0", "start_date": date.today().isoformat(),
    }, follow_redirects=True)
    assert resp.status_code == 200

    assert FeedBarnPlan.query.filter_by(barn_id=barn.id).count() == 0


def test_end_date_before_start_date_rejected(app, logged_in_client):
    barn = make_barn(barn_no="TIP-PLAN-3")
    ration = _make_ration()

    resp = logged_in_client.post("/feed/barn-plans/new", data={
        "barn_id": str(barn.id), "ration_id": str(ration.id),
        "daily_qty_per_animal_kg": "1.5",
        "start_date": "2026-06-10", "end_date": "2026-06-01",
    }, follow_redirects=True)
    assert resp.status_code == 200

    assert FeedBarnPlan.query.filter_by(barn_id=barn.id).count() == 0, \
        "خطة تغذية بتاريخ نهاية قبل بدايتها انحفظت"


def test_valid_plan_still_saves_normally(app, logged_in_client):
    barn = make_barn(barn_no="TIP-PLAN-4")
    ration = _make_ration()

    resp = logged_in_client.post("/feed/barn-plans/new", data={
        "barn_id": str(barn.id), "ration_id": str(ration.id),
        "daily_qty_per_animal_kg": "1.8", "start_date": date.today().isoformat(),
    }, follow_redirects=True)
    assert resp.status_code == 200

    plan = FeedBarnPlan.query.filter_by(barn_id=barn.id).first()
    assert plan is not None
    assert plan.daily_qty_per_animal_kg == 1.8
