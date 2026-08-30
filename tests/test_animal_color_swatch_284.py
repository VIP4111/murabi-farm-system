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


def test_animal_form_includes_shared_color_chips_script(app, logged_in_client):
    """بند إضافي 292 — خريطة الألوان صارت بملف مشترك واحد
    (app/static/color_chips.js) بدل ما تتكرر بكل شاشة."""
    resp = logged_in_client.get("/animals/new")
    assert b"color_chips.js" in resp.data


def test_color_hex_map_covers_all_seeded_defaults():
    """كل الألوان الافتراضية السبعة (`AnimalColor.seed_defaults`) لازم
    تكون بخريطة الألوان المشتركة، وإلا تطلع فقعة رمادية محايدة بدل
    لونها الحقيقي. "أصفر" أُضيف بند إضافي (2026-08-30) — طلبك الصريح."""
    with open("app/static/color_chips.js", encoding="utf-8") as f:
        content = f.read()
    for name in ("أبيض", "أسود", "أحمر", "بني", "رمادي", "أصفر", "مبرقش"):
        assert f"'{name}'" in content


def test_yellow_added_to_seed_defaults_idempotently(app):
    """بند إضافي (2026-08-30) — طلبك: "حط لي لون أصفر مع الألوان".
    seed_defaults صارت idempotent لكل اسم على حدة (نفس تصحيح Breed)
    عشان مزرعة عندها ألوان مسجَّلة من قبل تلتقط "أصفر" تلقائياً بمجرد
    إعادة استدعاء seed_defaults، بدون ما تكرر أي لون موجود أصلاً."""
    from app.extensions import db
    from app.models import AnimalColor

    AnimalColor.seed_defaults()
    before = AnimalColor.query.count()
    assert AnimalColor.query.filter_by(name="أصفر").first() is not None

    # استدعاء ثانٍ (يحاكي مزرعة عندها ألوان قديمة قبل هذا البند) — ما
    # يكرر أي لون.
    AnimalColor.seed_defaults()
    assert AnimalColor.query.count() == before
