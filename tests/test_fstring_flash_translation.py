"""بند إضافي (2026-08-31) — طلبك "هل بحثت عن فجوات في إضافة دواء" قاد
لاكتشاف فئة سادسة عشرة (بعد كل الفئات السابقة): flash(f'...') — رسائل
مبنية بـf-string مباشرة، غير مغلَّفة بـ_() إطلاقاً، منتشرة بـ7 ملفات
مختلفة (طريقة استخدام، كتالوج دواء، نوع مرض، عرض مرضي، بروتوكول علاج،
حظيرة مكررة، دور مكرر، جوال مكرر، مستودع، دفعة). ما كانت البحوث
السابقة تلقطها لأنها تبحث عن flash("...") أو flash(f"...") بصيغ محدَّدة
بس، مو كل أنماط f-string الممكنة."""
from app.extensions import db
from app.models import Role, User


def _make_owner_en(phone="0599999340"):
    role = Role.query.filter_by(name="owner").first()
    user = User(name="Owner EN Flash Test", phone=phone, role_id=role.id, language="en")
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_duplicate_usage_route_error_translates_for_english_user(app, client):
    owner = _make_owner_en()
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})

    client.post("/health/usage-routes/new", data={"name": "حقن عضل"})  # already seeded
    resp = client.post("/health/usage-routes/new", data={"name": "حقن عضل"}, follow_redirects=True)
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "موجودة بالقائمة أصلاً" not in body
    assert "already in the list" in body


def test_duplicate_barn_number_error_translates_for_english_user(app, client):
    from factories import make_barn
    make_barn(barn_no="DUP-EN-1")
    owner = _make_owner_en(phone="0599999341")
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})

    resp = client.post("/barns/new", data={
        "barn_no": "DUP-EN-1", "barn_name": "حظيرة مكررة",
    }, follow_redirects=True)
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "مستخدم من قبل" not in body
    assert "already in use" in body


def test_new_warehouse_success_message_translates_for_english_user(app, client):
    owner = _make_owner_en(phone="0599999342")
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})

    resp = client.post("/warehouses/new", data={"name": "مستودع اختبار", "warehouse_type": "feed"},
                        follow_redirects=True)
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "تم إنشاء مستودع" not in body
    assert "was created" in body
