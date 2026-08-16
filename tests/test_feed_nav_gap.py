"""بند إضافي 200 — القائمة الجانبية لـ"العلف" كانت تحتوي 4 روابط بس
(الحاسبة، FCR، الموازِن، المستودعات) بدون أي رابط لـ"مكوّنات العلف"
(شاشة الإضافة الفعلية) أو "حركة المخزون" (فيها خيار "وارد
(شراء/تعبئة)" — يعني الشراء) أو "خطط تغذية الحظائر". الشاشات كانت
موجودة وتشتغل، بس ما فيه أي طريق يوصلها من التنقّل — مستخدم عادي
يفتح "العلف" ما يلقى طريقة يضيف علف أو يسجّل شراء."""
from app.extensions import db
from app.models import Role, User


def test_feed_drawer_links_to_items_movements_and_barn_plans(app, client):
    role = Role.query.filter_by(name="owner").first()
    owner = User(name="مالك اختبار قائمة العلف", phone="0599999140", role_id=role.id, language="ar")
    owner.set_password("test1234")
    db.session.add(owner)
    db.session.commit()

    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    resp = client.get("/")
    body = resp.data.decode()
    assert '/feed/items"' in body
    assert '/feed/movements"' in body
    assert '/feed/barn-plans"' in body
