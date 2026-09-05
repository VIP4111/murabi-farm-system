"""بند إضافي 82 — توسيع تغطية الأوفلاين (نقطة 8 من قائمة نقاط الضعف).
منطق التخزين المؤقت الفعلي جافاسكربت خالص (Service Worker) وما يُختبَر
بـpytest — الاختبار الحقيقي حي بمتصفح فعلي (موثَّق بـMASTER_SPEC.md).
هذا الملف يتحقق بس إن الراوت يقدّم الملف الصحيح وإن منطق "قائمة
الاستثناء" (denylist) حلّ محل "قائمة السماح" (allowlist) القديمة."""


def test_service_worker_route_serves_updated_denylist_logic(logged_in_client):
    resp = logged_in_client.get("/sw.js")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "isCacheablePath" in body
    # SEC-01: تحوّلت السياسة من "قائمة استثناء" (denylist) إلى "قائمة سماح"
    # (allowlist) — لا يُخزَّن أي ردّ افتراضياً. راجع tests/js/sw.test.js.
    assert "EXCLUDED_PATH_PREFIXES" not in body
    assert "isOfflineFieldPage" in body
    assert "isPublicAsset" in body
    # المنطق القديم (allowlist) لازم يكون اختفى تماماً كتعريف فعلي — التأكيد
    # الحقيقي إن الاستبدال صار، مو بس إضافة (مذكورة بتعليق توثيقي بس، وهذا مقبول)
    assert "const OFFLINE_URL_PATTERNS" not in body
    assert "function isOfflineEnabledPath" not in body


def test_service_worker_route_has_correct_headers(logged_in_client):
    resp = logged_in_client.get("/sw.js")
    assert resp.headers["Service-Worker-Allowed"] == "/"
    assert resp.mimetype == "application/javascript"
