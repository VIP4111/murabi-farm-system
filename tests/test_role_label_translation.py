"""بند إضافي (2026-08-31) — طلبك المباشر بصورة شاشة حقيقية (تعديل
عضو الفريق): قائمة اختيار "الدور" كانت تعرض display_name الخام
(عربي دايماً) حتى بحساب إنجليزي بالكامل. `Role.name` عمود داخلي ثابت
معروف (owner/doctor/worker/nurse/accountant/viewer) للأدوار الجاهزة
الستة — يسمح بترجمة آمنة، بشرط إضافي: لو صاحب الحلال غيّر display_name
يدوياً، التعديل يبقى الأولوية (صفر ترجمة تتجاوز اسماً كتبه بنفسه)."""
from app.extensions import db
from app.models import Role, User


def _make_owner_en(phone="0599999350"):
    role = Role.query.filter_by(name="owner").first()
    user = User(name="Owner EN Role Test", phone=phone, role_id=role.id, language="en")
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_role_display_label_translates_default_name(app):
    role = Role.query.filter_by(name="doctor").first()
    assert role.display_label() == "الدكتور"  # لغة افتراضية عربي خارج سياق طلب


def test_role_display_label_respects_manual_rename(app):
    """لو صاحب الحلال غيّر display_name يدوياً، الاسم المخصَّص يبقى
    كما هو — صفر ترجمة تلقائية تتجاوزه."""
    role = Role.query.filter_by(name="doctor").first()
    role.display_name = "طبيب العيادة الخاص"
    db.session.commit()
    assert role.display_label() == "طبيب العيادة الخاص"


def test_member_edit_role_dropdown_translates_for_english_user(app, client):
    en_owner = _make_owner_en()
    client.post("/login", data={"phone": en_owner.phone, "password": "pass1234"})

    resp = client.get("/team/members/new")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert ">الدكتور<" not in body
    assert ">Doctor<" in body
    assert ">Owner<" in body
