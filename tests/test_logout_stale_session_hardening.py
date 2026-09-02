"""بند إصلاح — بلاغ مستخدم: أحياناً بعد تسجيل خروج من حساب وتسجيل
دخول ببيانات حساب ثاني فعلياً، يفتح النظام الحساب السابق بدل الجديد.
السبب الأرجح على شبكات المزرعة الضعيفة: شاشة تسجيل الدخول تُعرَض من
ذاكرة تخزين المتصفح (bfcache/cache) بدل نسخة جديدة من السيرفر. هذا
الإصلاح: تفريغ الجلسة صراحة عند الخروج + رؤوس no-cache على شاشة/رد
الدخول عشان ما يُعاد عرض نسخة قديمة بعد الخروج."""


def test_logout_response_has_no_cache_headers(app, logged_in_client):
    resp = logged_in_client.get("/logout")
    assert resp.headers.get("Cache-Control", "").startswith("no-store")


def test_login_page_response_has_no_cache_headers(client):
    resp = client.get("/login")
    assert resp.headers.get("Cache-Control", "").startswith("no-store")


def test_logout_then_login_as_different_user_lands_on_correct_account(app, client, owner, worker):
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    client.get("/logout")
    resp = client.post("/login", data={"phone": worker.phone, "password": "pass1234"}, follow_redirects=True)
    body = resp.data.decode()
    assert resp.status_code == 200
    assert owner.name not in body or worker.name in body
