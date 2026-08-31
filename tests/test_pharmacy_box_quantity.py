"""بند إضافي (2026-08-31) — طلبك الصريح: "لما تسجّل دواء جديد، يجب
توضيح مثل علبة كم ملي، عدد العلب" — عوض كتابة الكمية الإجمالية مباشرة
كرقم مجرَّد، تكتب عدد العلب وكمية العلبة الواحدة، والنظام يحسب
`available_qty` تلقائياً. اختياري تماماً — لو الحقلان فاضيَين، الإدخال
المباشر القديم يستمر يشتغل بدون أي تغيير."""
from app.extensions import db
from app.models.pharmacy import Pharmacy


def test_pharmacy_new_computes_available_qty_from_boxes(app, logged_in_client):
    resp = logged_in_client.post("/health/pharmacy/new", data={
        "name": "دواء بعلب", "box_count": "10", "box_quantity": "100",
        "min_stock_qty": "0", "unit": "مل",
    }, follow_redirects=True)
    assert resp.status_code == 200
    item = Pharmacy.query.filter_by(name="دواء بعلب").first()
    assert item is not None
    assert item.box_count == 10
    assert item.box_quantity == 100
    assert item.available_qty == 1000


def test_pharmacy_new_without_boxes_uses_direct_available_qty(app, logged_in_client):
    """السلوك القديم يبقى شغّالاً بدون أي تغيير لو ما استخدم المستخدم
    حقلَي العلب — صفر كسر لأي دواء يُسجَّل بالطريقة المباشرة."""
    resp = logged_in_client.post("/health/pharmacy/new", data={
        "name": "دواء بدون علب", "available_qty": "55",
        "min_stock_qty": "0", "unit": "حبة",
    }, follow_redirects=True)
    assert resp.status_code == 200
    item = Pharmacy.query.filter_by(name="دواء بدون علب").first()
    assert item is not None
    assert item.box_count is None
    assert item.box_quantity is None
    assert item.available_qty == 55


def test_pharmacy_edit_recomputes_available_qty_from_boxes(app, logged_in_client):
    item = Pharmacy(name="دواء للتعديل", available_qty=20)
    db.session.add(item)
    db.session.commit()

    resp = logged_in_client.post(f"/health/pharmacy/{item.id}/edit", data={
        "name": "دواء للتعديل", "box_count": "5", "box_quantity": "20",
        "min_stock_qty": "0", "unit": "مل",
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(item)
    assert item.box_count == 5
    assert item.box_quantity == 20
    assert item.available_qty == 100
