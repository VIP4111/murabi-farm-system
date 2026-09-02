"""بند إصلاح — بلاغ مستخدم بصورة شاشة: ضغط "الإعدادات" بحساب الدكتور
(ما عنده صلاحية settings.manage افتراضياً — تصرف صحيح ومتعمَّد) طلعت
له صفحة بيضا بنص إنجليزي خام من Flask ("Forbidden... read-protected")
بدل رسالة عربية مفهومة. القيد نفسه صحيح ومتعمَّد — الإصلاح بس بالرسالة."""


def test_forbidden_page_shows_arabic_friendly_message(app, client, worker):
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.get("/settings")
    body = resp.data.decode()
    assert resp.status_code == 403
    assert "Forbidden" not in body
    assert "ما تملك صلاحية الوصول" in body


def test_not_found_page_shows_arabic_friendly_message(app, logged_in_client):
    resp = logged_in_client.get("/this-page-does-not-exist-xyz")
    body = resp.data.decode()
    assert resp.status_code == 404
    assert "Not Found" not in body
    assert "الصفحة غير موجودة" in body
