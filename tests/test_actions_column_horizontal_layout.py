"""طلب المستخدم: صورة شاشة الصيدلية توضح أزرار (تعديل/المستودعات/جرد)
مكدَّسة عمودياً فوق بعض بشكل مزعج بالعين — السبب أن عمود الإجراءات
كان <td> عادي بدون class="actions-col"، فالأزرار (اللي تتحول لشكل
pill عبر CSS العام لـ `table.compact-table td a`) تلف كل وحدة بسطر
لحالها. الإصلاح: إضافة class="actions-col" يفعّل قاعدة flex-row
الموجودة أصلاً بـ base.html، فتصير الأزرار بجنب بعض أفقياً."""
from tests.factories import make_pharmacy, make_feed


def test_pharmacy_list_actions_column_uses_horizontal_layout(app, logged_in_client):
    with app.app_context():
        make_pharmacy(name="دواء اختبار التخطيط")
    resp = logged_in_client.get("/health/pharmacy")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'class="actions-col"' in body


def test_feed_items_list_actions_column_uses_horizontal_layout(app, logged_in_client):
    with app.app_context():
        make_feed(name="علف اختبار التخطيط")
    resp = logged_in_client.get("/feed/items")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'class="actions-col"' in body
