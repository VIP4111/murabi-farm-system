"""بند إضافي 284 — طلبك الصريح: "بحضت اسم اللون مثل ابيض ابيك تحط جنبه
فقعة بيضاء تطبقه على جميع الالوان". فقعة لونية حية جنب اختيار اللون
بشاشة تسجيل/تعديل الحيوان، بدل ما يبقى اسم نصي بحت."""


def test_animal_form_renders_color_chip_picker(app, logged_in_client):
    """بند إضافي 288 — طلبك الصريح "حطلي ألوان بدل الكتابة": القائمة
    النصية استُبدلت بفقاعات لونية فعلية تُضغط."""
    resp = logged_in_client.get("/animals/new")
    body = resp.data.decode()
    assert 'id="colorChips"' in body
    assert 'class="colorChip"' in body
    assert 'id="colorInput"' in body


def test_color_hex_map_covers_all_seeded_defaults(app, logged_in_client):
    """كل الألوان الافتراضية الستة (`AnimalColor.seed_defaults`) لازم
    تكون بخريطة الألوان بالجافاسكربت، وإلا تطلع فقعة رمادية محايدة
    بدل لونها الحقيقي."""
    resp = logged_in_client.get("/animals/new")
    body = resp.data.decode()
    for name in ("أبيض", "أسود", "أحمر", "بني", "رمادي", "مبرقش"):
        assert f"'{name}'" in body
