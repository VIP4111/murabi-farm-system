"""بند إضافي 209 (تتمة) — طلبك: "ودّي زر التطعيمات بالصفحة الرئيسية
يتسجّل عليه عدد التطعيمات المسجّلة لم يحين وقتها والتطعيمات المتأخرة"،
و"المساعد الذكي ما عنده علم بالمولود الجديد" — كلمات مفتاحية إضافية
لأسئلة المولود الشائعة (هل يتسجل تلقائي، متى الفطام...)."""
from datetime import date, timedelta

from app.assistant.knowledge_base import search
from app.assistant.text_utils import normalize
from app.extensions import db
from app.models import Role, User, Vaccination
from factories import make_animal


def _make_owner(phone="0599999210"):
    role = Role.query.filter_by(name="owner").first()
    user = User(name="مالك اختبار بطاقة التطعيمات", phone=phone, role_id=role.id, language="ar")
    user.set_password("test1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_home_shows_vaccination_counts(app, client):
    owner = _make_owner()
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    animal = make_animal(animal_no="VACHOME-01", price=500)
    db.session.add(Vaccination(
        animal_id=animal.id, vaccine_name="لقاح اختبار الرئيسية", date=date.today() - timedelta(days=10),
        next_due_date=date.today() - timedelta(days=2),
    ))
    db.session.commit()

    resp = client.get("/")
    body = resp.data.decode()
    assert "التطعيمات" in body
    assert "1 متأخرة" in body


def test_home_shows_no_scheduled_vaccinations_badge(app, client):
    owner = _make_owner(phone="0599999211")
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    resp = client.get("/")
    body = resp.data.decode()
    assert "لا يوجد تطعيمات مجدولة حالياً" in body


def test_newborn_auto_registration_question_matches_add_animal_entry():
    results = search(normalize("هل المولود يتسجل تلقائي"))
    assert results
    assert results[0].code == "howto_add_animal"


def test_weaning_question_matches_newborn_faq_entry():
    results = search(normalize("متى افطم المولود"))
    assert results
    assert results[0].code == "newborn_faq"
