"""بحث "مقاسات الجوال" (2026-09-06) — لقيت رسالة Flask-Login الافتراضية
("Please log in to access this page.") تطلع بالإنجليزي الخام لما تفتح
رابطاً مباشرة بدون تسجيل دخول — نفس فئة مشكلة صفحات 403/404/500/413
القديمة اللي صارت عربية، بس هذي فاتت لأنها نص Flask-Login نفسه، مو نص
كتبناه إحنا. الإصلاح: login_manager.login_message عربي."""


def test_unauthenticated_visit_shows_arabic_login_message(client):
    resp = client.get("/animals", follow_redirects=True)
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "سجّل دخولك أولاً عشان توصل لهذي الصفحة." in body
    assert "Please log in to access this page" not in body
