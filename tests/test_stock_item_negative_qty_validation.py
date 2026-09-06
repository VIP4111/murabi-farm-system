"""فحص عميق مقسَّم — تدقيق شامل للنماذج بعد إصلاح deduct_stock/
add_stock: لقينا نفس فئة الثغرة بمكان مختلف — شاشات "إضافة/تعديل"
صنف علف/معدة/دواء تُدخل الرصيد الافتتاحي (`available_qty`) و"الحد
الأدنى للمخزون" مباشرة بالسجل، بدون المرور بأي دالة محمية (`add_stock`/
`deduct_stock`). كمية سالبة كانت تُحفظ بصمت، وتكسر فحص "qty > available"
بكل عمليات الخصم اللاحقة (رصيد سالب أصلاً يخلي أي خصم موجب يبان "أكبر
من المتوفر" بالغلط)."""
from app.models import Feed, Equipment, Pharmacy


def test_new_feed_item_rejects_negative_available_qty(logged_in_client):
    resp = logged_in_client.post("/feed/items/new", data={
        "name": "علف اختبار سالب", "available_qty": "-5",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "سالباً" in resp.data.decode()
    assert Feed.query.filter_by(name="علف اختبار سالب").first() is None


def test_new_equipment_item_rejects_negative_available_qty(logged_in_client):
    resp = logged_in_client.post("/equipment/items/new", data={
        "name": "معدة اختبار سالب", "available_qty": "-3",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "سالباً" in resp.data.decode()
    assert Equipment.query.filter_by(name="معدة اختبار سالب").first() is None


def test_new_pharmacy_item_rejects_negative_available_qty(logged_in_client):
    resp = logged_in_client.post("/health/pharmacy/new", data={
        "name": "دواء اختبار سالب", "available_qty": "-2",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "سالباً" in resp.data.decode()
    assert Pharmacy.query.filter_by(name="دواء اختبار سالب").first() is None
