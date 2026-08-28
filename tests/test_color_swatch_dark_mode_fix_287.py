"""بند إضافي 287 — طلبك الصريح: "حطيت لون اصفر طلع لي بالدائرة لون
أسود، مين المسئول هنا اللون؟". السبب الحقيقي: اللون الاحتياطي للفقعة
(لأي لون مخصَّص غير موجود بخريطة الألوان الستة الافتراضية) كان
`var(--bg)` — خلفية الصفحة، اللي بالوضع الداكن قريبة جداً من الأسود،
فيبين وكأن النظام اختار أسود بالغلط. صار لوناً رمادياً ثابتاً (#d1d5db)
مع حد متقطّع، ما يتأثر بالوضع الداكن/الفاتح إطلاقاً، وواضح إنه
"غير معروف" مو لون حقيقي مُختار.

بند إضافي 292 — المنطق صار بملف مشترك (app/static/color_chips.js)
بدل ما يتكرر بكل شاشة، فالفحص هنا صار على الملف المشترك نفسه + تأكيد
إن الثلاث شاشات فعلاً تحمّله."""


def test_shared_color_chips_file_uses_fixed_neutral_fallback_not_theme_background():
    with open("app/static/color_chips.js", encoding="utf-8") as f:
        content = f.read()
    assert "UNKNOWN_COLOR_HEX = '#d1d5db'" in content
    # اللون الاحتياطي القديم (var(--bg)) ما يفترض يبقى بمنطق الفقعة
    # الحية نفسه — نتأكد إن الإصلاح فعلياً حل محله.
    assert "var(--bg)" not in content


def test_animal_form_loads_shared_color_chips_file(app, logged_in_client):
    resp = logged_in_client.get("/animals/new")
    assert b"color_chips.js" in resp.data


def test_bulk_purchase_loads_shared_color_chips_file(app, logged_in_client):
    resp = logged_in_client.get("/animals/bulk-purchase")
    assert b"color_chips.js" in resp.data


def test_batch_form_loads_shared_color_chips_file(app, logged_in_client):
    resp = logged_in_client.get("/batches/new")
    assert b"color_chips.js" in resp.data
