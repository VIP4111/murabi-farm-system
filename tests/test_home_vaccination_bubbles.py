"""بند إضافي 210 — طلبك: "الي طلبته منك وضع فقعة فيها رقم فوق زر
التطعيم، المطلوب إلغاء الشريط [البطاقة النصية] وتنفيذ [الفقعتين]".
استبدلنا بطاقة "التطعيمات" النصية ببند 209 بفقعتين ملوّنتين فوق زر
"التطعيمات" بالإجراءات السريعة: حمراء للمتأخر، برتقالية للقادم."""
from datetime import date, timedelta

from app.extensions import db
from app.models import Role, User, Vaccination
from factories import make_animal


def _make_owner(phone="0599999210"):
    role = Role.query.filter_by(name="owner").first()
    user = User(name="مالك اختبار فقعات التطعيم", phone=phone, role_id=role.id, language="ar")
    user.set_password("test1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_home_no_longer_shows_vaccination_card_text(app, client):
    owner = _make_owner()
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    resp = client.get("/")
    body = resp.data.decode()
    assert "كل التطعيمات المسجَّلة اللي لها موعد قادم" not in body


def test_home_shows_overdue_bubble_on_vaccinations_button(app, client):
    owner = _make_owner(phone="0599999211")
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    animal = make_animal(animal_no="VBUB-01")
    db.session.add(Vaccination(animal_id=animal.id, vaccine_name="لقاح فقعة",
                                date=date.today() - timedelta(days=30),
                                next_due_date=date.today() - timedelta(days=2)))
    db.session.commit()

    resp = client.get("/")
    body = resp.data.decode()
    assert 'notif-bubble overdue' in body
