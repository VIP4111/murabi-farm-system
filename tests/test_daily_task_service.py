"""اختبارات المهام اليومية التلقائية (بند إضافي 55.1) — البنود الثابتة
تُنشأ دائماً، البنود الشرطية تُنشأ فقط عند وجود سببها، ولا تكرار عند
استدعاء متكرر بنفس اليوم."""
from datetime import date, timedelta

from app.extensions import db
from app.core import daily_task_service as svc
from app.models import Disease, Task
from factories import make_animal


def test_always_on_rules_created_for_today_and_yesterday(app):
    created = svc.generate_daily_husbandry_tasks()
    titles = {t.title for t in created}
    assert "🔍 فحص يومي للقطيع" in titles
    assert "💧 فحص الماء والأملاح" in titles
    assert "🧹 تنظيف المعالف والحظائر" in titles
    # ثلاثة بنود ثابتة × يومين (اليوم وأمس) = 6 مهام على الأقل
    always_on_created = [t for t in created if t.title in (
        "🔍 فحص يومي للقطيع", "💧 فحص الماء والأملاح", "🧹 تنظيف المعالف والحظائر"
    )]
    assert len(always_on_created) == 6


def test_second_call_same_day_creates_nothing_new(app):
    first = svc.generate_daily_husbandry_tasks()
    second = svc.generate_daily_husbandry_tasks()
    assert len(first) > 0
    assert second == []


def test_newborn_review_only_created_when_recent_birth_exists(app):
    created = svc.generate_daily_husbandry_tasks()
    assert not any("🍼" in t.title for t in created)

    animal = make_animal(animal_no="DT-01")
    animal.birth_date = date.today() - timedelta(days=5)
    db.session.commit()

    created = svc.generate_daily_husbandry_tasks()
    assert any("🍼" in t.title for t in created)


def test_withdrawal_review_only_created_when_open_disease_exists(app):
    created = svc.generate_daily_husbandry_tasks()
    assert not any("💊" in t.title for t in created)

    animal = make_animal(animal_no="DT-02")
    db.session.add(Disease(animal_id=animal.id, disease_name="مرض اختبار",
                            date=date.today(), status="active"))
    db.session.commit()

    created = svc.generate_daily_husbandry_tasks()
    assert any("💊" in t.title for t in created)


def test_all_daily_tasks_created_as_suggested_status(app):
    created = svc.generate_daily_husbandry_tasks()
    assert created
    assert all(t.status == "suggested" for t in created)
    assert all(t.source_type == svc.SOURCE_TYPE for t in created)
