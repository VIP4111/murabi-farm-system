"""اختبارات خلطة العلف المجمَّعة لكل حظيرة + توزيعها الفعلي عند إنجاز
مهمة "وجبة علف" (بند إضافي 134) — يبني على موازِن العليقة الموجود
أصلاً (`optimize_blend`، بند 48) بس مجمَّع لكل رؤوس الحظيرة النشطة
بدل رأس واحد، وعلى مهمة "وجبة علف" الموجودة أصلاً (بند 131) بربط
إنجازها بخصم فعلي من المخزون."""
from datetime import date

from app.extensions import db
from app.feed import feed_service as feed_svc
from app.models import Feed, FeedMovement, Task
from app.team import task_service
from factories import make_animal, make_barn, make_feed


def _make_usable_feeds():
    make_feed(name="برسيم", unit_price=1.5, protein_percent=18, energy_kcal_per_kg=2400, available_qty=100)
    make_feed(name="شعير", unit_price=1.0, protein_percent=11, energy_kcal_per_kg=3000, available_qty=100)
    make_feed(name="تبن", unit_price=0.5, protein_percent=4, energy_kcal_per_kg=1800, available_qty=100)


def test_barn_daily_blend_feasible_with_weighed_animals(app):
    _make_usable_feeds()
    barn = make_barn(barn_no="FB-01")
    a1 = make_animal(animal_no="FA-01", barn_id=barn.id)
    a2 = make_animal(animal_no="FA-02", barn_id=barn.id)
    a1.weight = 40
    a2.weight = 35
    db.session.commit()

    result = feed_svc.barn_daily_blend(barn_id=barn.id)
    assert result["feasible"] is True
    assert result["animals_included"] == 2
    assert result["animals_skipped"] == 0
    total_qty = sum(b["quantity_kg"] for b in result["blend"])
    assert total_qty > 0


def test_barn_daily_blend_infeasible_without_weighed_animals(app):
    _make_usable_feeds()
    barn = make_barn(barn_no="FB-02")
    make_animal(animal_no="FA-03", barn_id=barn.id)  # no weight set

    result = feed_svc.barn_daily_blend(barn_id=barn.id)
    assert result["feasible"] is False
    assert result["animals_skipped"] == 1


def _make_feeding_task(barn, assignee):
    task = task_service.create_suggested_task(
        title="🥣 وجبة علف اختبار", task_type="feeding_schedule", barn_id=barn.id,
        due_date=date.today(), source_type="Test", source_id=1, auto_approve=True,
    )
    task.assignee_id = assignee.id
    db.session.commit()
    return task


def test_completing_feeding_task_deducts_stock(app, owner):
    _make_usable_feeds()
    barn = make_barn(barn_no="FB-03")
    a1 = make_animal(animal_no="FA-04", barn_id=barn.id)
    a1.weight = 40
    db.session.commit()

    barsim_before = Feed.query.filter_by(name="برسيم").first().available_qty

    task = _make_feeding_task(barn, owner)
    task_service.complete_task(task, actor=owner)

    barsim_after = Feed.query.filter_by(name="برسيم").first().available_qty
    assert barsim_after < barsim_before
    assert FeedMovement.query.filter_by(barn_id=barn.id, movement_type="out").count() > 0
    assert "خُصم من المخزون" in task.completion_note


def test_completing_feeding_task_without_weighed_animals_skips_deduction(app, owner):
    _make_usable_feeds()
    barn = make_barn(barn_no="FB-04")
    make_animal(animal_no="FA-05", barn_id=barn.id)  # no weight

    task = _make_feeding_task(barn, owner)
    task_service.complete_task(task, actor=owner)

    assert FeedMovement.query.filter_by(barn_id=barn.id, movement_type="out").count() == 0
    assert "ما تم خصم علف تلقائياً" in task.completion_note
    assert task.status == "done"


def test_completing_feeding_task_with_no_animals_skips_deduction(app, owner):
    _make_usable_feeds()
    barn = make_barn(barn_no="FB-05")

    task = _make_feeding_task(barn, owner)
    task_service.complete_task(task, actor=owner)

    assert task.status == "done"
    assert FeedMovement.query.filter_by(barn_id=barn.id, movement_type="out").count() == 0


def test_task_detail_page_shows_blend_preview(app, logged_in_client, owner):
    _make_usable_feeds()
    barn = make_barn(barn_no="FB-06")
    a1 = make_animal(animal_no="FA-06", barn_id=barn.id)
    a1.weight = 40
    db.session.commit()

    task = _make_feeding_task(barn, owner)
    resp = logged_in_client.get(f"/team/tasks/{task.id}")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "خلطة اليوم المقترحة" in body
    assert "برسيم" in body
