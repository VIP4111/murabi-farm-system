"""بند إضافي 287 — طلبك الصريح: "حطيت لون اصفر طلع لي بالدائرة لون
أسود، مين المسئول هنا اللون؟". السبب الحقيقي: اللون الاحتياطي للفقعة
(لأي لون مخصَّص غير موجود بخريطة الألوان الستة الافتراضية) كان
`var(--bg)` — خلفية الصفحة، اللي بالوضع الداكن قريبة جداً من الأسود،
فيبين وكأن النظام اختار أسود بالغلط. صار لوناً رمادياً ثابتاً (#d1d5db)
مع حد متقطّع، ما يتأثر بالوضع الداكن/الفاتح إطلاقاً، وواضح إنه
"غير معروف" مو لون حقيقي مُختار."""


def test_animal_form_swatch_uses_fixed_neutral_fallback_not_theme_background(app, logged_in_client):
    resp = logged_in_client.get("/animals/new")
    body = resp.data.decode()
    assert "UNKNOWN_COLOR_HEX = '#d1d5db'" in body
    # اللون الاحتياطي القديم (var(--bg)) ما يفترض يبقى بمنطق الفقعة
    # الحية نفسه — نتأكد إن الإصلاح فعلياً حل محله.
    assert "hex || 'var(--bg)'" not in body


def test_bulk_purchase_swatch_uses_fixed_neutral_fallback(app, logged_in_client):
    resp = logged_in_client.get("/animals/bulk-purchase")
    body = resp.data.decode()
    assert "UNKNOWN_COLOR_HEX = '#d1d5db'" in body
    assert "|| 'var(--bg)'" not in body


def test_batch_form_swatch_uses_fixed_neutral_fallback(app, logged_in_client):
    resp = logged_in_client.get("/batches/new")
    body = resp.data.decode()
    assert "UNKNOWN_COLOR_HEX = '#d1d5db'" in body
    assert "|| 'var(--bg)'" not in body
