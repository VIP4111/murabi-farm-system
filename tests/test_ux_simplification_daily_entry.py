"""بند إضافي (2026-08-31، طلبك المباشر: "تبسيط واجهة الإدخال اليومي...
نماذج سريعة وبسيطة تقلل عدد الحقول") — 3 تحسينات ملموسة:
1. اختصار "تسجيل مولود جديد" (?source=birth) يفتح فورم "حيوان جديد"
   بالمصدر معبّى مسبقاً (بطاقة مختصرة بدل قائمة اختيار)، مع رابط
   "تغيير" لمن يبي يبدّله فعلاً.
2. حقول ثانوية (اسم/وزن/سعر/صورة) صارت داخل قسم "تفاصيل إضافية
   (اختياري)" قابل للطي بدل ما تطول الفورم دايماً.
3. تلميحات مساعدة مصغّرة (مكوّن macros.tip) على حقول غير بديهية —
   "الغرض" بفورم الحيوان، و"الشدة"/"الكمية المستخدمة" بفورم تسجيل
   المرض.
+ شاشة "حركة مخزون علف" صار افتراضها "صادر" (الاستخدام اليومي الفعلي)
  بدل "وارد" (له شاشة شراء مخصَّصة أصلاً)."""
from app.extensions import db
from app.models import Role, User


def _owner_client(client, phone="0599999290"):
    role = Role.query.filter_by(name="owner").first()
    u = User(name="مالك اختبار الإدخال السريع", phone=phone, role_id=role.id)
    u.set_password("pass1234")
    db.session.add(u)
    db.session.commit()
    client.post("/login", data={"phone": u.phone, "password": "pass1234"})
    return u


def test_new_animal_form_default_has_no_prefill_banner(app, client):
    _owner_client(client)
    resp = client.get("/animals/new")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'id="sourcePrefillBanner" style="display:none' in body
    assert "تسجيل حيوان جديد" in body


def test_new_animal_form_with_birth_source_shows_prefill_banner_and_title(app, client):
    _owner_client(client)
    resp = client.get("/animals/new?source=birth")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert "تسجيل مولود جديد" in body
    assert 'id="sourceSelectWrap" style="display:none' in body
    assert "ولادة بالمزرعة" in body
    assert 'id="changeSourceLink"' in body


def test_new_animal_form_ignores_invalid_source_query_param(app, client):
    """دفاع بعمق — قيمة غير معروفة بـ?source= ما تكسر الشاشة ولا تُعتبر
    تعبئة مسبقة صالحة."""
    _owner_client(client)
    resp = client.get("/animals/new?source=hacked")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'id="sourcePrefillBanner" style="display:none' in body


def test_birth_source_animal_still_saves_correctly_end_to_end(app, client):
    """الفحص الحاسم — التعبئة المسبقة تأثير عرض بس، الحفظ الفعلي يبقى
    يشتغل بنفس منطق المسار العادي تماماً."""
    from app.models import Animal, Barn, AnimalColor
    from tests.factories import make_animal

    _owner_client(client)
    barn = Barn.query.first() or Barn(barn_no="B-UX1", barn_name="حظيرة اختبار")
    if not barn.id:
        db.session.add(barn)
    color = AnimalColor.query.first() or AnimalColor(name="أبيض")
    if not color.id:
        db.session.add(color)
    db.session.commit()
    mother = make_animal(animal_no="UX-MOM-01", gender="أنثى")

    resp = client.post("/animals/new", data={
        "source": "birth", "gender": "أنثى", "species": "sheep_goat",
        "barn_id": str(barn.id), "color": color.name, "mother_id": str(mother.id),
    }, follow_redirects=True)
    assert resp.status_code == 200
    animal = Animal.query.filter_by(barn_id=barn.id).order_by(Animal.id.desc()).first()
    assert animal is not None
    assert animal.source.value == "birth"


def test_home_page_has_birth_shortcut_for_users_with_animals_manage(app, client):
    _owner_client(client)
    resp = client.get("/")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert "source=birth" in body
    assert "تسجيل مولود" in body


def test_additional_details_section_collapsed_by_default_for_new_animal(app, client):
    _owner_client(client)
    resp = client.get("/animals/new")
    body = resp.data.decode()
    assert "<details class=\"drawer-group\" >" in body or '<details class="drawer-group">' in body
    assert "تفاصيل إضافية" in body


def test_info_tip_macro_renders_on_animal_form(app, client):
    _owner_client(client)
    resp = client.get("/animals/new")
    body = resp.data.decode()
    assert 'class="info-tip"' in body
    assert "info-tip-bubble" in body


def test_feed_movement_form_defaults_to_out(app, client):
    _owner_client(client)
    resp = client.get("/feed/movements/new")
    body = resp.data.decode()
    assert resp.status_code == 200
    idx = body.index('name="movement_type"')
    snippet = body[idx: idx + 200]
    assert 'value="out" selected' in snippet
