"""بند إضافي (2026-08-31) — طلبك الصريح: "احتاج تضيف في كل الصفحات
زر رجوع". أضيف زر عام واحد بـbase.html (رأس كل صفحة، جنب زر القائمة
الجانبية) بدل تكرار الإضافة بكل قالب على حدة — يستخدم history.back()
(يرجّعك بالضبط لآخر صفحة زرتها)، ويرجع للرئيسية بدل ما يبقى بلا أثر
لو ما فيه سجل تصفّح فعلي (مثلاً رابط مباشر بتبويب جديد)."""

BACK_BUTTON_ONCLICK = 'onclick="goBackOrHome()"'


def test_back_button_shows_on_non_home_page(app, logged_in_client):
    resp = logged_in_client.get("/animals/new")
    assert resp.status_code == 200
    assert BACK_BUTTON_ONCLICK in resp.data.decode()


def test_back_button_hidden_on_home_page(app, logged_in_client):
    resp = logged_in_client.get("/")
    assert resp.status_code == 200
    assert BACK_BUTTON_ONCLICK not in resp.data.decode()


def test_back_button_hidden_before_login(app, client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert BACK_BUTTON_ONCLICK not in resp.data.decode()
