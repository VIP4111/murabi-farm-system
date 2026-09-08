"""بند إصلاح (فحص عميق — طلبك: "افحص جميع النوافذ بعمق") — تبويبات
فلترة المهام حسب الدور، وقائمة "المنفَّذين" بشاشة تفاصيل البلاغ، كانتا
تستخدمان `Role.display_name` الخام بدل `Role.display_label()`
الجاهزة، نفس فجوة قائمة السلالة بالضبط. وأداة "فحص سلامة البيانات"
كانت عربي بحت بدون `_()`."""
from flask_babel import force_locale

from app.extensions import db
from app.models import Role, User
from app.team.routes import _role_tabs
from app.core import data_integrity_service


def test_role_tabs_translate_to_english(app):
    with force_locale("en"):
        tabs = dict(_role_tabs())
    assert "doctor" in tabs
    assert str(tabs["doctor"]) == "Doctor"
    assert str(tabs["doctor"]) != "الدكتور"


def test_data_integrity_labels_translate_to_english(app):
    from app.models import VetVisit, Animal
    from tests.factories import make_animal
    animal = make_animal(animal_no="ORPHAN-1")
    animal_id = animal.id
    db.session.add(VetVisit(date=__import__("datetime").date.today(), doctor_id=1, animal_id=999999))
    db.session.commit()
    with force_locale("en"):
        issues = data_integrity_service.run_full_audit()
    labels = [str(i["label"]) for i in issues]
    assert any("orphan" in l.lower() or "vet" in l.lower() for l in labels)
