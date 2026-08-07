"""بند إضافي — طلبك: "دخلت على الحظائر لحظت كلمة تعديل ابيك تخليها
بشكل زر وتلونه". نفس أسلوب بند 140 (تحويل رقم الحيوان/المرحلة لأزرار)."""
from factories import make_barn


def test_barns_list_edit_link_renders_as_colored_button(logged_in_client):
    make_barn(barn_no="BTN-01")
    resp = logged_in_client.get("/barns")
    body = resp.get_data(as_text=True)
    assert 'class="btn" href="' in body
    assert "تعديل" in body
