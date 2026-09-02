"""طلبك المباشر: "اضف فقعه بسم شرح طريقة الاستخدام لكل زر" (شاشة
المساعد الذكي) — مكوّن macros.tip العام (بُني قبلها لتبسيط شاشات
الإدخال اليومي) طُبِّق على كل زر/تبويب رئيسي بشاشة المساعد الذكي."""


def test_assistant_chat_page_shows_tooltips_on_main_controls(app, logged_in_client):
    resp = logged_in_client.get("/assistant/")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert body.count('class="info-tip"') >= 6
    assert "info-tip-bubble" in body
