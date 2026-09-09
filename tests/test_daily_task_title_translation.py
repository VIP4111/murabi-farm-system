"""بند إصلاح (فحص عميق — طلبك: "افحص جميع النوافذ بعمق") — عناوين
المهام اليومية التلقائية الأربعة الثابتة كانت تُخزَّن عربي بحت وقت
الإنشاء وتبقى مجمَّدة كذلك للأبد بغض النظر عن لغة من يشوف المهمة
لاحقاً. `Task.title_key` + `display_title()`/`display_notes()` يحلّان
المشكلة بترجمة وقت العرض، بدون المساس بـ`title`/`notes` الخام
(العامل الذي أنشأها أول مرة يشوفها بنفس اللغة دائماً — سلوك تاريخي
محفوظ)."""
from datetime import date, datetime

from app.extensions import db
from app.models import Role, User, Disease
from app.models.task import Task, TASK_TITLE_TRANSLATIONS
from app.core import daily_task_service
from tests.factories import make_animal
from flask_babel import force_locale


def test_task_display_title_translates_when_title_key_set(app):
    task = Task(title="🚧 مراجعة العزل والحجر", task_type="daily_husbandry",
                title_key="daily_isolation_review",
                notes="راجع الحيوانات الجديدة أو المريضة في حظيرة العزل قبل خلطها بالقطيع.")
    db.session.add(task)
    db.session.commit()
    with force_locale("en"):
        assert task.display_title() == TASK_TITLE_TRANSLATIONS["daily_isolation_review"]["title_en"]
        assert task.display_notes() == TASK_TITLE_TRANSLATIONS["daily_isolation_review"]["notes_en"]
    with force_locale("ar"):
        assert task.display_title() == "🚧 مراجعة العزل والحجر"


def test_task_display_title_falls_back_when_no_title_key(app):
    task = Task(title="مهمة يدوية مخصَّصة", task_type="custom")
    db.session.add(task)
    db.session.commit()
    with force_locale("en"):
        assert task.display_title() == "مهمة يدوية مخصَّصة"


def test_generated_daily_tasks_carry_title_key_for_known_rules(app):
    animal = make_animal(animal_no="DAILY-TASK-1")
    db.session.add(Disease(animal_id=animal.id, disease_name="مرض اختبار", date=date(2026, 1, 10), status="active"))
    db.session.commit()
    created = daily_task_service.generate_daily_husbandry_tasks(now=datetime(2026, 1, 15, 10, 0))
    keyed = [t for t in created if t.title_key]
    assert keyed  # مرض مفتوح يفعّل قاعدة "daily_withdrawal_review" الثابتة
    for t in keyed:
        assert t.title_key in TASK_TITLE_TRANSLATIONS


def test_task_list_screen_shows_english_title_for_english_doctor(app, client):
    role = Role.query.filter_by(name="doctor").first()
    doctor = User(name="English Doctor", phone="0500099601", role_id=role.id, language="en")
    doctor.set_password("pass1234")
    db.session.add(doctor)
    task = Task(title="⚖️ مراجعة الفطام والفرز", task_type="daily_husbandry",
                title_key="daily_weaning_review", status="pending", assignee_id=None)
    db.session.add(task)
    db.session.commit()

    client.post("/login", data={"phone": doctor.phone, "password": "pass1234"})
    resp = client.get("/team/tasks")
    assert resp.status_code == 200
    assert b"Weaning" in resp.data
