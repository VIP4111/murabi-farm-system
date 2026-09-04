"""بلاغ مستخدم حقيقي (متكرر): "أسوي خروج من حساب الدكتور ما يطلع" —
يضغط "خروج"، يرجعه النظام لصفحة الرئيسية وهو لسا داخل بالحساب.

السبب: تسجيل الدخول دايماً يستخدم `login_user(user, remember=True)`
(كوكي "تذكّرني" منفصلة عن كوكي الجلسة). `logout_user()` يعلّم
`session['_remember'] = 'clear'` — هذي الإشارة اللي يعتمد عليها
Flask-Login بعد الطلب عشان يحذف كوكي "تذكّرني" فعلياً من المتصفح.
لكن `session.clear()` (المضافة بإصلاح سابق لمشكلة bfcache) كانت تمسح
هذا العلم بالذات *قبل* ما يوصل دوره — فكوكي "تذكّرني" تبقى صالحة رغم
الخروج، وأول طلب بعدها (حتى لصفحة /login نفسها) يعيد تسجيل الدخول
تلقائياً وبصمت عبرها، و`login()` عندها "لو مسجّل دخول، ودّيه الرئيسية"
— فيبان تماماً وكإن "خروج" ما سوى شي."""


def test_logout_deletes_remember_cookie(app, logged_in_client):
    resp = logged_in_client.get("/logout")
    set_cookie_headers = resp.headers.get_all("Set-Cookie")
    remember_cookie_deleted = any(
        "remember_token=" in h and ("Max-Age=0" in h or "expires=Thu, 01-Jan-1970" in h)
        for h in set_cookie_headers
    )
    assert remember_cookie_deleted, f"remember_token cookie was not cleared: {set_cookie_headers}"


def test_visiting_login_after_logout_does_not_bounce_back_to_home(app, client, owner):
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    client.get("/logout")
    resp = client.get("/login")
    assert resp.status_code == 200
    assert b"login" in resp.request.path.encode() or resp.status_code == 200
    assert resp.headers.get("Location") is None


def test_logout_then_visiting_protected_page_requires_real_login(app, client, owner):
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    client.get("/logout")
    resp = client.get("/team/tasks")
    assert resp.status_code == 302
    assert "/login" in resp.headers.get("Location", "")
