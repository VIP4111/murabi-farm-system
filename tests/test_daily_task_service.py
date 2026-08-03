"""اختبارات المهام اليومية التلقائية (بند إضافي 55.1) — البنود الثابتة
تُنشأ دائماً، البنود الشرطية تُنشأ فقط عند وجود سببها، ولا تكرار عند
استدعاء متكرر بنفس اليوم. `now=` مثبَّت بوقت صباحي صريح بكل استدعاء
(بند إضافي 72 أضاف سلوكاً يعتمد على الساعة — بدون تثبيتها، الاختبارات
تصير عرضة للفشل حسب وقت تشغيلها الفعلي بعد الساعة 6 مساءً)."""
from datetime import date, datetime, timedelta

from app.extensions import db
from app.core import daily_task_service as svc
from app.models import Disease, Task
from factories import make_animal

MORNING = datetime.combine(date.today(), datetime.min.time()) + timedelta(hours=9)


def test_always_on_rules_created_for_today_and_yesterday(app):
    created = svc.generate_daily_husbandry_tasks(now=MORNING)
    titles = {t.title for t in created}
    assert "🔍 فحص يومي للقطيع" in titles
    assert "💧 فحص الماء والأملاح" in titles
    assert "🧹 تنظيف المعالف والحظائر" in titles
    # ثلاثة بنود ثابتة × يومين (اليوم وأمس، قبل الساعة 6 مساءً) = 6 مهام
    always_on_created = [t for t in created if t.title in (
        "🔍 فحص يومي للقطيع", "💧 فحص الماء والأملاح", "🧹 تنظيف المعالف والحظائر"
    )]
    assert len(always_on_created) == 6


def test_second_call_same_day_creates_nothing_new(app):
    first = svc.generate_daily_husbandry_tasks(now=MORNING)
    second = svc.generate_daily_husbandry_tasks(now=MORNING)
    assert len(first) > 0
    assert second == []


def test_newborn_review_only_created_when_recent_birth_exists(app):
    created = svc.generate_daily_husbandry_tasks(now=MORNING)
    assert not any("🍼" in t.title for t in created)

    animal = make_animal(animal_no="DT-01")
    animal.birth_date = date.today() - timedelta(days=5)
    db.session.commit()

    created = svc.generate_daily_husbandry_tasks(now=MORNING)
    assert any("🍼" in t.title for t in created)


def test_withdrawal_review_only_created_when_open_disease_exists(app):
    created = svc.generate_daily_husbandry_tasks(now=MORNING)
    assert not any("💊" in t.title for t in created)

    animal = make_animal(animal_no="DT-02")
    db.session.add(Disease(animal_id=animal.id, disease_name="مرض اختبار",
                            date=date.today(), status="active"))
    db.session.commit()

    created = svc.generate_daily_husbandry_tasks(now=MORNING)
    assert any("💊" in t.title for t in created)


def test_all_daily_tasks_created_as_pending_status(app):
    # بند إضافي 107 — توصل تلقائياً للعامل بدون انتظار اعتماد الدكتور
    # (خلافاً لبقية المهام التلقائية بالنظام، اللي تبقى "مقترحة").
    created = svc.generate_daily_husbandry_tasks(now=MORNING)
    assert created
    assert all(t.status == "pending" for t in created)
    assert all(t.source_type == svc.SOURCE_TYPE for t in created)


def test_tomorrow_tasks_not_generated_before_evening(app):
    created = svc.generate_daily_husbandry_tasks(now=MORNING)
    tomorrow = date.today() + timedelta(days=1)
    assert not any(t.due_date == tomorrow for t in created)


def test_tomorrow_tasks_generated_from_six_pm(app):
    evening = datetime.combine(date.today(), datetime.min.time()) + timedelta(hours=18)
    created = svc.generate_daily_husbandry_tasks(now=evening)
    tomorrow = date.today() + timedelta(days=1)
    tomorrow_created = [t for t in created if t.due_date == tomorrow]
    assert len(tomorrow_created) == 3  # نفس الثلاثة بنود الثابتة


def test_tomorrow_tasks_not_generated_at_five_fifty_nine_pm(app):
    almost_evening = datetime.combine(date.today(), datetime.min.time()) + timedelta(hours=17, minutes=59)
    created = svc.generate_daily_husbandry_tasks(now=almost_evening)
    tomorrow = date.today() + timedelta(days=1)
    assert not any(t.due_date == tomorrow for t in created)
