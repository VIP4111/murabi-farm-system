"""بلاغ مستخدم حقيقي: "الصورة (الشعار) بالرئيسية تختفي وترجع بشكل
مستمر". السبب: على إنترنت ضعيف باستمرار، `MURABI_STALE_PAGE_REFRESHED`
(راجع app/static/sw.js) يطلب من التبويب `location.reload()` — وهذا
التحديث نفسه يدخل بنفس سباق الشبكة/المهلة، فلو الشبكة ما زالت بطيئة
يتكرر التحديث بلا توقف (حلقة لا نهائية تبان كأن الصفحة/الشعار يومض).
الإصلاح: حارس تبريد (cooldown) بذاكرة التبويب (sessionStorage) يمنع
أكثر من تحديث تلقائي واحد لكل رابط خلال 15 ثانية.

نفس نمط `test_service_worker.py` (فحص شحن الكود الفعلي بالصفحة المرسَلة
للمتصفح — منطق JavaScript صرف داخل قالب Jinja، ما يُختبَر تنفيذياً
بـpytest)."""


def test_home_page_ships_the_reload_cooldown_guard(logged_in_client):
    resp = logged_in_client.get("/")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "AUTO_RELOAD_COOLDOWN_MS" in body
    assert "murabi_last_auto_reload" in body
    # الحارس لازم يتحقق فعلياً قبل location.reload() جوّا مستمع الرسائل،
    # مو بس يكون معرَّفاً بمكان منفصل بلا استخدام
    listener_start = body.index("MURABI_STALE_PAGE_REFRESHED")
    listener_end = body.index("location.reload();", listener_start)
    listener_body = body[listener_start:listener_end]
    assert "murabi_last_auto_reload" in listener_body
