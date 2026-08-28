"""بند إضافي 284 — طلبك الصريح: "بحضت اسم اللون مثل ابيض ابيك تحط جنبه
فقعة بيضاء تطبقه على جميع الالوان". فقعة لونية حية جنب اختيار اللون
بشاشة تسجيل/تعديل الحيوان، بدل ما يبقى اسم نصي بحت."""


def test_animal_form_renders_color_swatch_element(app, logged_in_client):
    resp = logged_in_client.get("/animals/new")
    body = resp.data.decode()
    assert 'id="colorSwatch"' in body
    assert 'id="colorSelect"' in body


def test_color_hex_map_covers_all_seeded_defaults(app, logged_in_client):
    """كل الألوان الافتراضية الستة (`AnimalColor.seed_defaults`) لازم
    تكون بخريطة الألوان بالجافاسكربت، وإلا تطلع فقعة رمادية محايدة
    بدل لونها الحقيقي."""
    resp = logged_in_client.get("/animals/new")
    body = resp.data.decode()
    for name in ("أبيض", "أسود", "أحمر", "بني", "رمادي", "مبرقش"):
        assert f"'{name}'" in body
