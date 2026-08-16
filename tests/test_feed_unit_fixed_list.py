"""بند إضافي 202 — "الوحدة" بمكوّن العلف كانت حقل نص حر ("كجم"/"كيلو"/
"كيلوجرام" حسب من كتبها)، وهذا كان يكسر فعلياً منطق تجميع "الأصناف
البديلة" بتقرير طلب الشراء (بند 156) — يقارن الوحدة حرفياً، فصنفين
نفس الوحدة الحقيقية بصيغتين مختلفتين يُعامَلان كوحدتين مختلفتين
بالغلط. صارت قائمة ثابتة (Feed.UNITS) تُعرض بفورم الإضافة/التعديل
كـ<select>، مع رفض أي قيمة خارج القائمة والرجوع للافتراضي."""
from app.extensions import db
from app.models import Role, User, Feed


def _make_owner(phone="0599999150"):
    role = Role.query.filter_by(name="owner").first()
    user = User(name="مالك اختبار وحدة العلف", phone=phone, role_id=role.id, language="ar")
    user.set_password("test1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_item_new_form_shows_fixed_unit_dropdown(app, client):
    owner = _make_owner()
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    resp = client.get("/feed/items/new")
    body = resp.data.decode()
    assert '<select name="unit">' in body
    for u in Feed.UNITS:
        assert f'<option value="{u}"' in body


def test_item_new_accepts_valid_unit_from_list(app, client):
    owner = _make_owner(phone="0599999151")
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    client.post("/feed/items/new", data={
        "name": "علف اختبار الوحدة الصحيحة", "unit": "لتر", "available_qty": "10",
    })
    item = Feed.query.filter_by(name="علف اختبار الوحدة الصحيحة").first()
    assert item is not None
    assert item.unit == "لتر"


def test_item_new_rejects_arbitrary_unit_defaults_to_kg(app, client):
    """محاولة إرسال قيمة خارج القائمة مباشرة (تجاوز الفورم) — يرجع
    للافتراضي بدل ما يخزّن نص حر تعسفي يكسر تجميع بند 156 من جديد."""
    owner = _make_owner(phone="0599999152")
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    client.post("/feed/items/new", data={
        "name": "علف اختبار وحدة تعسفية", "unit": "كيلوجرام مضبوط", "available_qty": "10",
    })
    item = Feed.query.filter_by(name="علف اختبار وحدة تعسفية").first()
    assert item is not None
    assert item.unit == "كجم"


def test_item_new_accepts_bale_unit_with_weight_kg(app, client):
    """بند إضافي 202 — "ربطة" (زي ربطة البرسيم) وحدها ما يكفي لأن وزنها
    مو ثابت عالمياً، فحقل unit_weight_kg اختياري يسجّل مرجع "كم كيلو
    بالربطة" الخاص بصاحب الحلال، دون أي حساب تلقائي يعتمد عليه."""
    owner = _make_owner(phone="0599999154")
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    client.post("/feed/items/new", data={
        "name": "برسيم ربطة اختبار", "unit": "ربطة", "unit_weight_kg": "15",
        "available_qty": "20",
    })
    item = Feed.query.filter_by(name="برسيم ربطة اختبار").first()
    assert item is not None
    assert item.unit == "ربطة"
    assert item.unit_weight_kg == 15.0


def test_item_new_leaves_unit_weight_kg_empty_when_not_provided(app, client):
    owner = _make_owner(phone="0599999155")
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    client.post("/feed/items/new", data={
        "name": "علف اختبار بلا وزن وحدة", "unit": "كيس", "available_qty": "5",
    })
    item = Feed.query.filter_by(name="علف اختبار بلا وزن وحدة").first()
    assert item is not None
    assert item.unit_weight_kg is None


def test_item_edit_form_preselects_current_unit(app, client):
    owner = _make_owner(phone="0599999153")
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    item = Feed(name="علف اختبار تعديل الوحدة", unit="طن", available_qty=5, status="active")
    db.session.add(item)
    db.session.commit()

    resp = client.get(f"/feed/items/{item.id}/edit")
    body = resp.data.decode()
    assert '<option value="طن" selected>' in body


def test_item_edit_form_prefills_unit_weight_kg(app, client):
    owner = _make_owner(phone="0599999156")
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    item = Feed(name="علف اختبار وزن الوحدة بالتعديل", unit="ربطة", unit_weight_kg=15.0,
                available_qty=5, status="active")
    db.session.add(item)
    db.session.commit()

    resp = client.get(f"/feed/items/{item.id}/edit")
    body = resp.data.decode()
    assert 'name="unit_weight_kg"' in body
    assert 'value="15.0"' in body
