"""SEC-01 (تدقيق 2026-09-04، البوابة أ) — الجانب الخادمي من إصلاح تسريب كاش
الـService Worker بين مستخدمي الجهاز الواحد.

الجانب الأخطر من التسريب كان `/settings/backup/export-now`: مسار **GET**
يعيد تفريغاً كاملاً لقاعدة البيانات (79 جدولاً — هاشات كلمات المرور، وثائق
هوية العمالة، الرواتب، رمزا وصول حيّان)، وأي ردّ GET ناجح كان قابلاً للتخزين
بكاش المتصفح ويبقى فيه بعد الخروج. تفريغ كامل للقاعدة لا يجوز أن يكون طلباً
GET قابلاً للتخزين أو التشغيل برابط — صار POST محمياً بـCSRF.

(منطق الـService Worker نفسه جافاسكربت صرف، مُختبَر بـ`tests/js/sw.test.js`.)
"""
import json


def _login(client, phone, password="pass1234"):
    return client.post("/login", data={"phone": phone, "password": password}, follow_redirects=True)


# ---------- export-now: GET مرفوض، POST هو المسار الوحيد ----------

def test_export_now_rejects_get(app, logged_in_client, owner):
    """الحارس الأساسي — GET لتفريغ القاعدة كان هو ما يجعله قابلاً للتخزين
    بكاش الـService Worker وقابلاً للتشغيل بأي رابط/prefetch."""
    resp = logged_in_client.get("/settings/backup/export-now")
    assert resp.status_code == 405


def test_export_now_post_returns_downloadable_json(app, logged_in_client, owner):
    resp = logged_in_client.post("/settings/backup/export-now")
    assert resp.status_code == 200
    assert resp.mimetype == "application/json"
    assert "attachment" in resp.headers.get("Content-Disposition", "")
    data = json.loads(resp.data.decode("utf-8"))
    assert "tables" in data


def test_export_now_post_still_requires_settings_manage(app, client, worker):
    _login(client, worker.phone)
    resp = client.post("/settings/backup/export-now")
    assert resp.status_code == 403


def test_export_now_post_creates_audit_log_entry(app, logged_in_client, owner):
    from app.models import AuditLog

    logged_in_client.post("/settings/backup/export-now")
    entry = AuditLog.query.filter_by(action="backup.export_json").order_by(AuditLog.id.desc()).first()
    assert entry is not None
    assert entry.actor_user_id == owner.id


def test_export_now_get_does_not_create_audit_log_entry(app, logged_in_client, owner):
    """GET المرفوض لازم يكون بلا أي أثر جانبي — لا تفريغ ولا تسجيل."""
    from app.models import AuditLog

    logged_in_client.get("/settings/backup/export-now")
    assert AuditLog.query.filter_by(action="backup.export_json").count() == 0


def test_settings_backup_page_uses_post_form_not_plain_link(app, logged_in_client, owner):
    """الواجهة لازم تُرسل POST حقيقياً بحماية CSRF — رابط `<a href>` كان
    يجعل التفريغ الكامل يبدأ بنقرة عادية (أو prefetch من المتصفح)."""
    resp = logged_in_client.get("/settings/backup")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "/settings/backup/export-now" in body
    # لا رابط GET مباشر للمسار
    assert 'href="/settings/backup/export-now"' not in body
    # فورم POST يستهدفه ويحمل رمز CSRF
    form_start = body.index('action="/settings/backup/export-now"')
    form_open = body.rfind("<form", 0, form_start)
    form_close = body.index("</form>", form_start)
    form_html = body[form_open:form_close]
    assert 'method="post"' in form_html.lower()
    assert 'name="csrf_token"' in form_html
    assert "تنزيل نسخة احتياطية كاملة الآن" in form_html


# ---------- الـService Worker المُقدَّم يحمل إصلاح SEC-01 ----------

def test_served_sw_has_all_five_defence_layers_and_bumped_cache(app, logged_in_client):
    """يتحقق إن النسخة المُقدَّمة فعلياً على /sw.js (لا ملف بالمستودع
    وحسب) تحوي طبقات الإصلاح الخمس، وإن إصدار الكاش تجاوز v7 الملوَّث."""
    resp = logged_in_client.get("/sw.js")
    assert resp.status_code == 200
    body = resp.data.decode()
    # (أ) قائمة سماح — لا قائمة استثناء، ولا استثناء لأي صفحة
    assert "isPublicAsset" in body
    assert "isOfflineFieldPage" not in body
    assert "EXCLUDED_PATH_PREFIXES" not in body
    # (هـ) إشعار التبويبات المفتوحة عند حدّ المصادقة، مع استثناء التبويب
    # المُنتقِل نفسه — بدونه يعيد تحميل نفسه ويُجهض انتقاله لـ/logout.
    assert "notifyClientsOfAuthBoundary" in body
    assert "MURABI_AUTH_BOUNDARY" in body
    assert "event.clientId" in body
    # (ب) مسح عند حدّ المصادقة
    assert "AUTH_BOUNDARY_PREFIXES" in body
    assert "isAuthBoundaryNavigation" in body
    assert "purgeAllCaches" in body
    # (ج) عدم تخزين التنزيلات
    assert "Content-Disposition" in body
    # (د) حارس الحقبة للرد المتأخر
    assert "mayCommitCache" in body
    assert "currentCacheEpoch" in body
    # أداة التحقق بعد النشر: الـSW يردّ بإصداره لمن يسأله (نسخة قديمة لا
    # تعرف هذه الرسالة فلا تردّ — وغياب الرد هو الدليل على عدم الترقية).
    assert "MURABI_SW_VERSION" in body
    assert "buildVersionReply" in body
    # إصدار الكاش تجاوز v7 الملوَّث
    assert 'murabi-offline-v7"' not in body


def test_no_html_page_is_on_the_offline_allowlist(app, logged_in_client):
    """قائمة السماح يجب أن تبقى `/static/` وحدها. قياس فعلي (2026-09-05)
    أثبت أن كل صفحة HTML — بما فيها الخمس التي اعتُبرت "ميدانية آمنة" —
    تحمل اسم المستخدم ورمز CSRF الخاص بجلسته، فلا صفحة تُخزَّن إطلاقاً.
    هذا حارس ضد إعادة إدخال استثناء صامت لاحقاً."""
    import re

    body = logged_in_client.get("/sw.js").data.decode()
    # لا ثوابت استثناء صفحات
    assert "OFFLINE_FIELD_PAGE" not in body
    # isCacheablePath يعتمد isPublicAsset وحدها
    fn = body[body.index("function isCacheablePath"):]
    fn = fn[:fn.index("\n}")]
    assert "isPublicAsset" in fn
    assert re.search(r"return\s+isPublicAsset\(url\.pathname\);", fn), fn
    # وisPublicAsset محصورة بـ/static/
    pub = body[body.index("function isPublicAsset"):]
    pub = pub[:pub.index("\n}")]
    assert '"/static/"' in pub


def test_precache_list_is_empty(app, logged_in_client):
    """التخزين المسبق عند التثبيت كان يخزّن أربع صفحات — أي جلسة أول من
    يفتح التطبيق. أُفرِغ بـSEC-01."""
    import re

    body = logged_in_client.get("/sw.js").data.decode()
    m = re.search(r"const PRECACHE_URLS = \[(.*?)\]", body, re.S)
    assert m, "PRECACHE_URLS غير موجود"
    assert not re.findall(r'"([^"]+)"', m.group(1)), "PRECACHE_URLS يجب أن يبقى فارغاً"


def test_offline_submission_queue_is_independent_of_the_page_cache(app, logged_in_client):
    """SEC-01 × DATA-01 — مسح الكاش يجب ألا يمسّ طابور الإدخالات غير
    المرسَلة: الطابور بـIndexedDB (`offline_sync.js`) والمسح على Cache
    Storage (`caches`) — مخزنان منفصلان تماماً بالمتصفح. نتحقق برمجياً
    أن كود المسح لا يلمس IndexedDB إطلاقاً، وأن الطابور لا يُخزَّن بالكاش."""
    sw = logged_in_client.get("/sw.js").data.decode()
    purge_body = sw[sw.index("function purgeAllCaches"):]
    purge_body = purge_body[:purge_body.index("\n}")]
    for forbidden in ("indexedDB", "murabi_offline", "pending_submissions", "deleteDatabase"):
        assert forbidden not in purge_body, forbidden
    # والـSW ككل لا يلمس قاعدة الطابور بأي موضع
    for forbidden in ("indexedDB", "deleteDatabase"):
        assert forbidden not in sw, forbidden
