"""اختبار بند التصميم "بلاطات مراح" + إصلاح ترجمة (طلبك: "ارجع افحص
ولي ما طبقت عليها طبقها") — دفعة سادسة: اتضح إن ثلاث أعمدة كانت
مفترَضة "نص حر" غلط بالفحوصات السابقة، وفعلياً مجموعات ثابتة تحتاج
ترجمة + شارة ملوّنة: نوع الحظيرة، غرض وصفة العلف، وفئة مكوّن العلف
(الأخيرة كان فيها خلل ترجمة كامن أيضاً — `_(c)` بمتغيّر داخل القائمة
المنسدلة القديمة ما كانت تُستخرَج بـpybabel إطلاقاً). + شارة إضافية
لعمود "القسم" بسجل الجرد (كان مترجَماً صح أصلاً، بس بدون تلوين)."""
from datetime import date

from app.extensions import db
from app.models import Feed
from app.models.feed import FeedRation
from app.models.inventory_count import InventoryCount
from tests.factories import make_barn


def _make_english_client(client):
    from app.models import Role, User
    role = Role.query.filter_by(name="owner").first()
    user = User(name="English Owner", phone="0500009200", role_id=role.id, language="en")
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    client.post("/login", data={"phone": user.phone, "password": "pass1234"})
    return client


def test_barns_list_translates_and_colors_barn_type(client):
    en_client = _make_english_client(client)
    make_barn(barn_no="B-TEST", barn_type="عزل")

    resp = en_client.get("/barns")
    assert resp.status_code == 200
    assert b"barn-type-chip" in resp.data
    assert b"Isolation" in resp.data
    assert "عزل".encode() not in resp.data


def test_rations_list_translates_and_colors_purpose(client):
    en_client = _make_english_client(client)
    ration = FeedRation(name="وصفة اختبار", purpose="حمل_متأخر")
    db.session.add(ration)
    db.session.commit()

    resp = en_client.get("/feed/rations")
    assert resp.status_code == 200
    assert b"ration-purpose-chip" in resp.data
    assert b"Late pregnancy" in resp.data
    assert "حمل متأخر".encode() not in resp.data


def test_feed_items_list_translates_and_colors_category(client):
    en_client = _make_english_client(client)
    item = Feed(name="علف اختبار", available_qty=10, unit="كجم", status="active", category="دريس")
    db.session.add(item)
    db.session.commit()

    resp = en_client.get("/feed/items")
    assert resp.status_code == 200
    assert b"feed-class-chip" in resp.data
    assert b"Hay" in resp.data
    assert "دريس".encode() not in resp.data


def test_inventory_counts_list_shows_kind_chip(logged_in_client):
    row = InventoryCount(kind="feed", item_id=1, item_name="صنف اختبار",
                          count_date=date.today(), expected_qty=10, actual_qty=9, diff_qty=-1)
    db.session.add(row)
    db.session.commit()

    resp = logged_in_client.get("/warehouses/inventory-counts")
    assert resp.status_code == 200
    assert b"count-kind-chip" in resp.data
