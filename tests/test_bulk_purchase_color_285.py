"""بند إضافي 285 — طلبك الصريح بعد صورة شاشة "الاستقبال الجماعي":
"في الاستقبال الجماعي... لا يوجد لون". الشاشة كانت تُنشئ رؤوساً بلون
فاضي دائماً، خلافاً لشاشة "+ حيوان جديد" الفردية اللي تفرضه إلزامياً."""
from app.extensions import db
from app.models import Animal


def test_bulk_purchase_form_shows_color_column(app, logged_in_client):
    """بند إضافي 288 — طلبك الصريح "حطلي ألوان بدل الكتابة"."""
    resp = logged_in_client.get("/animals/bulk-purchase")
    body = resp.data.decode()
    assert 'name="color_0"' in body
    assert "colorChip" in body


def test_bulk_purchase_route_saves_chosen_color(app, logged_in_client):
    resp = logged_in_client.post("/animals/bulk-purchase", data={
        "purchase_date": "2026-08-28", "species": "sheep_goat", "row_count": "1",
        "animal_no_0": "BPR-01", "gender_0": "ذكر", "color_0": "أبيض",
        "weight_0": "30", "price_0": "500",
    })
    assert resp.status_code == 302
    animal = Animal.query.filter_by(animal_no="BPR-01").first()
    assert animal is not None
    assert animal.color == "أبيض"


def test_bulk_purchase_route_rejects_row_without_color(app, logged_in_client):
    resp = logged_in_client.post("/animals/bulk-purchase", data={
        "purchase_date": "2026-08-28", "species": "sheep_goat", "row_count": "1",
        "animal_no_0": "BPR-02", "gender_0": "ذكر", "color_0": "",
        "weight_0": "30", "price_0": "500",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "لازم تحدد اللون".encode() in resp.data
    assert Animal.query.filter_by(animal_no="BPR-02").first() is None
