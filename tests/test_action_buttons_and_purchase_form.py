"""بند إضافي 207 — طلبك: (1) أزرار "تعديل"/"المستودعات" وأمثالها
بقوائم النظام كانت نص عادي بدون أي شكل زر — مسح شامل حوّلها لأزرار
بلون فارق (عبر إضافة class="compact-table" لجداول كانت ناقصتها،
تفعيل قاعدة `table.compact-table td a` الموجودة أصلاً بالنظام).
(2) فورم "شراء علف/معدات": زر "+ إضافة مكون/صنف جديد" جنب القائمة
المنسدلة، وتوضيح حي لـ"الوحدة" وإجمالي الكيلوجرامات التقريبي وقت
إدخال الكمية — يجاوب سؤالك "كيف النظام يفهم كم كيلو عشان يقسمها على
الحظائر/الرؤوس؟"."""
from app.extensions import db
from app.models import Role, User, Feed, Equipment


def _make_owner(phone="0599999200"):
    role = Role.query.filter_by(name="owner").first()
    user = User(name="مالك اختبار الأزرار والشراء", phone=phone, role_id=role.id, language="ar")
    user.set_password("test1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_feed_items_list_table_has_compact_table_class(app, client):
    owner = _make_owner()
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    resp = client.get("/feed/items")
    body = resp.data.decode()
    assert 'table class="compact-table"' in body
    assert "· <a" not in body


def test_pharmacy_list_table_has_compact_table_class(app, client):
    owner = _make_owner(phone="0599999201")
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    resp = client.get("/health/pharmacy")
    body = resp.data.decode()
    assert 'table class="compact-table"' in body


def test_feed_purchase_form_has_add_item_shortcut_and_unit_hint(app, client):
    owner = _make_owner(phone="0599999202")
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    feed = Feed(name="علف اختبار فورم الشراء", unit="ربطة", unit_weight_kg=15.0,
                available_qty=5, status="active")
    db.session.add(feed)
    db.session.commit()

    resp = client.get("/feed/purchase")
    body = resp.data.decode()
    assert "إضافة مكون جديد" in body
    assert 'data-unit="ربطة"' in body
    assert 'data-unit-weight="15.0"' in body
    assert "unitHint" in body


def test_equipment_purchase_form_has_add_item_shortcut(app, client):
    owner = _make_owner(phone="0599999203")
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    item = Equipment(name="معدة اختبار فورم الشراء", unit="قطعة", available_qty=2, status="active")
    db.session.add(item)
    db.session.commit()

    resp = client.get("/equipment/purchase")
    body = resp.data.decode()
    assert "إضافة صنف جديد" in body
