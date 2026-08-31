"""بند إضافي (2026-08-31) — طلبك المباشر: توسيع ميزة الاسم الإنجليزي
الاختياري (بُنيت أول مرة للحظائر) لتشمل السلالة/اللون/نوع المرض —
نفس معمارية `SpeciesType` بالنسبة للفصيلة، بس هذي الثلاث ما عندها
`code` ثابت يميّز "قيمة افتراضية" عن "إدخال مستخدم حر"، فكل قيمة
(حتى المزروعة افتراضياً) تُترجَم فقط لو المستخدم أضاف لها اسماً
إنجليزياً بنفسه — صفر ترجمة تلقائية لبيانات حرة.

**ملاحظة تقنية اكتُشفت أثناء كتابة هذي الاختبارات**: تسجيل دخول
مستخدمَين مختلفَين (لغتَين مختلفتَين) بنفس عميل اختبار وحد (client)
ضمن نفس دالة اختبار — حتى مع logout صريح بينهما — يعطّل تحديد اللغة
الصحيح للطلب الثاني (خلل موجود مسبقاً بآلية تخزين اللغة المؤقت لعميل
الاختبار، غير مرتبط بهذا البند، وغير مؤثر على الإنتاج الحقيقي حيث كل
طلب HTTP فعلي مستقل تماماً). الحل: كل اختبار يستخدم client/تسجيل
دخول واحد بس، نفس نمط كل الاختبارات الناجحة السابقة هذي الجلسة."""
from app.extensions import db
from app.models import Role, User
from app.models.animal_options import Breed, AnimalColor
from app.models.health import DiseaseType


def _make_owner_en(phone="0599999330"):
    role = Role.query.filter_by(name="owner").first()
    user = User(name="Owner EN RefList Test", phone=phone, role_id=role.id, language="en")
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_breed_display_label_falls_back_to_arabic_without_english_name(app):
    breed = Breed(name="نعيمي")
    db.session.add(breed)
    db.session.commit()
    assert breed.display_label() == "نعيمي"


def test_breed_new_form_saves_english_name(app, client, owner):
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    client.post("/animals/breeds/new", data={"name": "سلالة اختبار", "name_en": "Test Breed"},
                follow_redirects=True)
    breed = Breed.query.filter_by(name="سلالة اختبار").first()
    assert breed is not None
    assert breed.name_en == "Test Breed"


def test_breed_dropdown_shows_english_name_for_english_user(app, client):
    breed = Breed(name="سلالة اختبار٢", name_en="Second Test Breed")
    db.session.add(breed)
    db.session.commit()

    en_owner = _make_owner_en()
    client.post("/login", data={"phone": en_owner.phone, "password": "pass1234"})
    resp = client.get("/animals/new")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "Second Test Breed" in body
    assert ">سلالة اختبار٢<" not in body


def test_animal_color_new_form_saves_english_name(app, client, owner):
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    client.post("/animals/colors/new", data={"name": "لون اختبار", "name_en": "Test Color"},
                follow_redirects=True)
    color = AnimalColor.query.filter_by(name="لون اختبار").first()
    assert color is not None
    assert color.name_en == "Test Color"


def test_color_chip_title_shows_english_name_for_english_user(app, client):
    color = AnimalColor(name="لون اختبار٢", name_en="Second Test Color")
    db.session.add(color)
    db.session.commit()

    en_owner = _make_owner_en(phone="0599999331")
    client.post("/login", data={"phone": en_owner.phone, "password": "pass1234"})
    resp = client.get("/animals/new")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert 'title="Second Test Color"' in body


def test_disease_type_new_form_saves_english_name(app, client, owner):
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    client.post("/health/disease-types/new", data={"name": "مرض اختبار", "name_en": "Test Disease"},
                follow_redirects=True)
    dt = DiseaseType.query.filter_by(name="مرض اختبار").first()
    assert dt is not None
    assert dt.name_en == "Test Disease"
