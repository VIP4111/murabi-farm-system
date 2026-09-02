"""بند إصلاح — بلاغ مستخدم بفيديو: بدّل الوضع الليلي بشاشة "صفحة
اليوم"، وبعد الرجوع لصفحة الرئيسية رجعت الشاشة نهارية رغم إن التفضيل
محفوظ فعلياً بحسابه. السبب الأرجح: استرجاع صفحة سابقة من ذاكرة
المتصفح (bfcache) بدل طلب نسخة جديدة من السيرفر — نفس فئة مشكلة
"يرجعني حساب قديم بعد تسجيل الخروج" المُصلَحة سابقاً. الحل: أي صفحة
تُسترجَع من bfcache تُجبَر على تحديث حقيقي فوري."""


def test_base_template_forces_reload_on_bfcache_restore(app, logged_in_client):
    resp = logged_in_client.get("/")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert "pageshow" in body
    assert "event.persisted" in body
    assert "location.reload()" in body


def test_theme_toggle_persists_to_user_account(app, logged_in_client, owner):
    resp = logged_in_client.post("/settings/theme", data={"theme": "dark"}, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        from app.models import User
        refreshed = User.query.get(owner.id)
        assert refreshed.theme == "dark"
    # أي صفحة ثانية تُفتح بعدها لازم تجيب data-theme="dark" فعلياً من
    # السيرفر (مو من نسخة قديمة) — يتأكد إن السيرفر نفسه صحيح، والمشكلة
    # كانت طبقة عرض المتصفح (bfcache) لا منطق السيرفر.
    resp2 = logged_in_client.get("/")
    assert 'data-theme="dark"' in resp2.data.decode()
