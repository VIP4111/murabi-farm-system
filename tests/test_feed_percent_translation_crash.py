"""بند إضافي 200 — كل شاشات "العلف" المترجمة (بند 165(1)) كانت تنهار
بخطأ 500 فعلياً: `_('بروتين%')` وأشباهها فيها علامة % حرفية داخل نص
قابل للترجمة — Flask-Babel/Jinja يعامل % كصيغة تنسيق (string formatting)
ويرمي `ValueError: incomplete format` عند العرض. هذا كان السبب الحقيقي
وراء شكوى المستخدم "ما حصلت اضافة اعلاف" — شاشة الإضافة نفسها
(item_form.html) كانت تنهار قبل حتى ما توصلها."""
from app.extensions import db
from app.models import Role, User, Feed, FeedRation


def _make_owner(phone="0599999141"):
    role = Role.query.filter_by(name="owner").first()
    user = User(name="مالك اختبار العلف", phone=phone, role_id=role.id, language="ar")
    user.set_password("test1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_feed_items_list_does_not_crash(app, client):
    owner = _make_owner()
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    resp = client.get("/feed/items")
    assert resp.status_code == 200
    assert "بروتين%" in resp.data.decode()


def test_feed_item_new_form_does_not_crash(app, client):
    owner = _make_owner(phone="0599999142")
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    resp = client.get("/feed/items/new")
    assert resp.status_code == 200
    assert "بروتين خام %" in resp.data.decode()


def test_feed_item_new_form_actually_submits(app, client):
    owner = _make_owner(phone="0599999143")
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    resp = client.post("/feed/items/new", data={
        "name": "علف اختبار الإضافة", "protein_percent": "16", "available_qty": "100",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert Feed.query.filter_by(name="علف اختبار الإضافة").first() is not None


def test_ration_form_and_list_do_not_crash(app, client):
    owner = _make_owner(phone="0599999144")
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    resp = client.get("/feed/rations/new")
    assert resp.status_code == 200
    assert "100%" in resp.data.decode()
    resp2 = client.get("/feed/rations")
    assert resp2.status_code == 200


def test_feed_calculator_page_does_not_crash(app, client):
    owner = _make_owner(phone="0599999145")
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    resp = client.get("/feed/calculator")
    assert resp.status_code == 200


def test_english_locale_feed_pages_do_not_crash(app, client):
    """أهم اختبار — الانهيار الأصلي كان يظهر بس لما الترجمة الفعلية
    تُطبَّق (locale != ar)، عربي المصدر يمر بصمت لأنه نفس الـmsgid."""
    role = Role.query.filter_by(name="owner").first()
    user = User(name="Owner EN test", phone="0599999146", role_id=role.id, language="en")
    user.set_password("test1234")
    db.session.add(user)
    db.session.commit()
    client.post("/login", data={"phone": user.phone, "password": "test1234"})
    for path in ("/feed/items", "/feed/items/new", "/feed/rations", "/feed/rations/new", "/feed/calculator"):
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} crashed under English locale"
