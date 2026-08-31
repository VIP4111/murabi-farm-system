"""بند إضافي (2026-08-31) — طلبك المباشر بصورة شاشة حقيقية: خيارَي
قائمة "الفصيلة" بشاشة تسجيل حيوان جديد ("حلال (ضأن/ماعز)"/"نعام")
طلعا عربياً خاماً حتى بحساب إنجليزي بالكامل. `SpeciesType.label_ar`
نص حر مخزَّن بقاعدة البيانات (نفس مبدأ `Breed`/`AnimalColor`) — لكن
الاثنين الافتراضيَين لهما `code` ثابت معروف (`sheep_goat`/`ostrich`)
يسمح بترجمة آمنة بدون المساس بأي فصيلة مخصَّصة يضيفها المستخدم لاحقاً."""
from app.extensions import db
from app.models import Role, User
from app.models.animal_options import SpeciesType


def _make_owner_en(phone="0599999320"):
    role = Role.query.filter_by(name="owner").first()
    user = User(name="Owner EN Species Test", phone=phone, role_id=role.id, language="en")
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_species_dropdown_translates_for_english_user(app, client):
    SpeciesType.seed_defaults()
    owner = _make_owner_en()
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})

    resp = client.get("/animals/new")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "ضأن/ماعز" not in body
    assert ">نعام<" not in body
    assert "sheep/goat" in body.lower()
    assert "ostrich" in body.lower()


def test_species_dropdown_stays_arabic_for_arabic_user(app, client, owner):
    SpeciesType.seed_defaults()
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})

    resp = client.get("/animals/new")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "ضأن/ماعز" in body


def test_custom_species_name_stays_as_entered_regardless_of_language(app, client):
    """فصيلة مخصَّصة يضيفها المستخدم (نص حر بدون code معروف) تبقى كما
    كتبها بالضبط — صفر ترجمة تلقائية، نفس مبدأ اسم الحظيرة الحر."""
    SpeciesType.seed_defaults()
    custom = SpeciesType(code="custom_llama", label_ar="لاما مخصَّصة")
    db.session.add(custom)
    db.session.commit()

    owner = _make_owner_en(phone="0599999321")
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})

    resp = client.get("/animals/new")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "لاما مخصَّصة" in body
