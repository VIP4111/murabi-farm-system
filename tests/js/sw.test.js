// بند إضافي 83 — أول اختبارات آلية جافاسكربت بالمشروع (نقطة 9 من قائمة
// نقاط الضعف). يشغّلها Node.js المدمج (node:test)، بدون أي حزمة npm
// إضافية: `node --test tests/js/`
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const {
  isCacheablePath, keysToEvict, MAX_CACHE_ENTRIES,
  raceNetworkWithTimeout, NETWORK_TIMEOUT_MS, shouldCacheResponse,
  buildStaleReloadMessage, notifyClientsOfFreshData,
  CACHE_NAME, AUTH_BOUNDARY_PREFIXES, isAuthBoundaryNavigation, purgeAllCaches,
  endedAtLogin, precacheUrls, PRECACHE_URLS,
  isPublicAsset, isOfflineFieldPage, OFFLINE_FIELD_PAGE_EXACT, OFFLINE_FIELD_PAGE_PREFIXES,
  currentCacheEpoch, mayCommitCache,
} = require("../../app/static/sw.js");

const ORIGIN = "https://murabi-farm-system.onrender.com";

test("isCacheablePath (allowlist): allowlisted field pages → true", () => {
  assert.equal(isCacheablePath(ORIGIN + "/team/tasks", ORIGIN), true);
  assert.equal(isCacheablePath(ORIGIN + "/team/tasks/5", ORIGIN), true);
  assert.equal(isCacheablePath(ORIGIN + "/team/reports", ORIGIN), true);
  assert.equal(isCacheablePath(ORIGIN + "/", ORIGIN), true);
  assert.equal(isCacheablePath(ORIGIN + "/today", ORIGIN), true);
  assert.equal(isCacheablePath(ORIGIN + "/alerts/mine", ORIGIN), true);
});

test("isCacheablePath (allowlist): public /static/ assets → true", () => {
  assert.equal(isCacheablePath(ORIGIN + "/static/offline_sync.js", ORIGIN), true);
  assert.equal(isCacheablePath(ORIGIN + "/static/icons/icon-32.png", ORIGIN), true);
});

test("isCacheablePath (allowlist): DEFAULT-DENY — anything not allowlisted → false", () => {
  // تغيّر سلوكي مقصود (SEC-01): صفحات محمية/مرتبطة بمستخدم لم تعد تُخزَّن
  // افتراضياً، حتى لو ليست بأي "قائمة استثناء". العمل الميداني الحرج
  // (طابور الإدخالات data-offline) مستقل تماماً عن كاش الصفحات هذا.
  for (const path of ["/animals/5", "/health/pharmacy", "/repro/matings",
                      "/feed/", "/batches/new", "/warehouses/", "/ostrich/",
                      "/equipment/", "/climate/"]) {
    assert.equal(isCacheablePath(ORIGIN + path, ORIGIN), false, path);
  }
});

test("isCacheablePath: uploads / login / logout are never cached (بند 82 + SEC-01)", () => {
  // كانت "قائمة استثناء" صريحة؛ صارت مغطّاة بـdefault-deny لقائمة السماح.
  for (const path of ["/uploads/images/x.jpg", "/login", "/login/quick", "/logout"]) {
    assert.equal(isCacheablePath(ORIGIN + path, ORIGIN), false, path);
  }
});

test("isCacheablePath: cross-origin request → false", () => {
  assert.equal(isCacheablePath("https://evil.com/team/tasks", ORIGIN), false);
});

test("isCacheablePath: malformed URL → false, never throws", () => {
  assert.equal(isCacheablePath("not a url", ORIGIN), false);
});

test("isPublicAsset / isOfflineFieldPage: exact building blocks of the allowlist", () => {
  assert.equal(isPublicAsset("/static/x.js"), true);
  assert.equal(isPublicAsset("/team/tasks"), false);
  assert.equal(isOfflineFieldPage("/team/tasks"), true);
  assert.equal(isOfflineFieldPage("/team/tasks/5"), true);
  assert.equal(isOfflineFieldPage("/team/reports/new"), true);
  assert.equal(isOfflineFieldPage("/finance/"), false);
  assert.equal(isOfflineFieldPage("/settings"), false);
  // "/team/reports" (بلاغات ميدانية) مسموح، لكن "/reports" (تحليلي) لا
  assert.equal(isOfflineFieldPage("/reports/"), false);
  assert.equal(isOfflineFieldPage("/reports/sales"), false);
});

// بند إضافي 91 (نقطة 7) — تقليم الكاش بدون حد أقصى سابق
test("keysToEvict: under the limit → nothing to evict", () => {
  const urls = Array.from({ length: 50 }, (_, i) => `${ORIGIN}/page/${i}`);
  assert.deepEqual(keysToEvict(urls, MAX_CACHE_ENTRIES), []);
});

test("keysToEvict: over the limit → evicts oldest first (FIFO)", () => {
  const urls = Array.from({ length: 155 }, (_, i) => `${ORIGIN}/page/${i}`);
  const evicted = keysToEvict(urls, 150);
  assert.equal(evicted.length, 5);
  assert.deepEqual(evicted, urls.slice(0, 5));
});

test("keysToEvict: exactly at the limit → nothing to evict", () => {
  const urls = Array.from({ length: 150 }, (_, i) => `${ORIGIN}/page/${i}`);
  assert.deepEqual(keysToEvict(urls, 150), []);
});

// بند إضافي 201 — قبل هذا البند، fetch() لطلب على شبكة ميتة فعلياً (لا
// خطأ سيرفر، بس صفر اتصال) ممكن يعلّق طويل جداً على iOS Safari تحديداً
// قبل ما يرفض الوعد، فمستخدم الآيفون يشوف "تحميل" بلا نهاية بدل النسخة
// المخزَّنة اللي كانت جاهزة. هذي الاختبارات تتحقق من سلوك السباق نفسه
// بمعزل عن بيئة Service Worker حقيقية (بدون محاكاة self/caches كاملة).
test("raceNetworkWithTimeout: fast network response wins over timeout", async () => {
  const fastNetwork = Promise.resolve("network-response");
  const result = await raceNetworkWithTimeout(fastNetwork, 4000, (ms) => new Promise(() => {})); // timeout never fires
  assert.equal(result, "network-response");
});

test("raceNetworkWithTimeout: network that never resolves falls back to timeout (null)", async () => {
  const hangingNetwork = new Promise(() => {}); // يحاكي fetch() المعلَّق على شبكة ميتة
  const fastTimeout = (ms) => Promise.resolve(null); // مهلة "تنتهي فوراً" وقت الاختبار
  const result = await raceNetworkWithTimeout(hangingNetwork, 4000, fastTimeout);
  assert.equal(result, null);
});

test("NETWORK_TIMEOUT_MS: a real, sane value (not accidentally 0 or absurdly long)", () => {
  assert.ok(NETWORK_TIMEOUT_MS > 0 && NETWORK_TIMEOUT_MS <= 10000);
});

// إصلاح — بلاغ مستخدم حقيقي: "حفظت الحيوان وسوا لي خروج" (يبان وكإنه
// طلع من حسابه رغم إن جلسته سليمة) — السبب كان تخزين صفحة تسجيل الدخول
// المُعاد توجيهها إليها تحت مفتاح الرابط الأصلي، فتُعرض بدل الصفحة
// الحقيقية أي مرة الشبكة تتأخر وتُستخدم النسخة المخزَّنة.
test("shouldCacheResponse: a normal successful page → cacheable", () => {
  assert.equal(shouldCacheResponse({ ok: true, url: "https://x.test/animals/5" }), true);
});

test("shouldCacheResponse: a response that redirected to /login → never cached", () => {
  assert.equal(shouldCacheResponse({ ok: true, url: "https://x.test/login?next=%2Fanimals%2F5" }), false);
});

test("shouldCacheResponse: a non-ok response (error page) → never cached", () => {
  assert.equal(shouldCacheResponse({ ok: false, url: "https://x.test/animals/5" }), false);
});

test("shouldCacheResponse: null/undefined response → never cached, never throws", () => {
  assert.equal(shouldCacheResponse(null), false);
  assert.equal(shouldCacheResponse(undefined), false);
});

// إصلاح — بلاغ مستخدم: "احفظ بيانات حيوان، والبيانات ما ترتفع بنفس
// اللحظة — بس لو سويت خروج ودخول ترجع صحيحة" — لما الشبكة تتأخر ونعرض
// نسخة مخزَّنة قديمة، لازم نبلّغ الصفحة المفتوحة أول ما يوصل الرد
// الطازج فعلاً عشان تحدّث نفسها تلقائياً بدل ما تبقى عالقة بنسخة قديمة.
test("buildStaleReloadMessage: carries the exact url to reload", () => {
  const msg = buildStaleReloadMessage("https://x.test/animals/5");
  assert.equal(msg.type, "MURABI_STALE_PAGE_REFRESHED");
  assert.equal(msg.url, "https://x.test/animals/5");
});

test("notifyClientsOfFreshData: posts the reload message to every open window client", async () => {
  const posted = [];
  const fakeClients = [
    { postMessage: (m) => posted.push(m) },
    { postMessage: (m) => posted.push(m) },
  ];
  await notifyClientsOfFreshData("https://x.test/animals/5", () => Promise.resolve(fakeClients));
  assert.equal(posted.length, 2);
  assert.equal(posted[0].type, "MURABI_STALE_PAGE_REFRESHED");
  assert.equal(posted[0].url, "https://x.test/animals/5");
});

test("notifyClientsOfFreshData: no open clients → resolves without throwing", async () => {
  const result = await notifyClientsOfFreshData("https://x.test/animals/5", () => Promise.resolve([]));
  assert.deepEqual(result, []);
});


// ============================================================
// SEC-01 (تدقيق 2026-09-04) — كاش الـService Worker كان مشتركاً بين كل
// مستخدمي الجهاز الواحد: كاش واحد مفتاحه الرابط فقط، لا يُمسح عند
// الخروج، ويُقدَّم كلما تأخّرت الشبكة 4 ثوانٍ — فعامل يدخل بعد المالك
// على نفس اللوح يشوف صفحات المالك (المالية، الرواتب، سجل التدقيق).
// الإصلاح بثلاث طبقات مستقلة، كلٌّ منها مُختبَرة هنا:
//   (أ) استثناء الشاشات الحسّاسة قليلة القيمة أوفلاين من التخزين أصلاً،
//   (ب) مسح الكاش كاملاً عند أي "حدّ مصادقة" (/login أو /logout)،
//   (ج) عدم تخزين أي ردّ تنزيل (Content-Disposition: attachment).
// ============================================================

test("SEC-01(أ): sensitive owner/admin screens are never cached (now by default-deny)", () => {
  const sensitive = [
    "/settings", "/settings/backup", "/settings/audit", "/settings/readiness",
    "/finance/", "/finance/health", "/finance/export",
    "/team/salaries", "/team/payroll", "/team/payroll/reports", "/team/members",
    "/team/travel-history/3/update",
    "/reports/", "/reports/sales", "/reports/activity",
    "/assistant/", "/assistant/farm-notes",
  ];
  for (const path of sensitive) {
    assert.equal(isCacheablePath(ORIGIN + path, ORIGIN), false, path);
  }
});

test("SEC-01(أ): excluding /reports (analytics) must NOT exclude /team/reports (field reports)", () => {
  assert.equal(isCacheablePath(ORIGIN + "/team/reports", ORIGIN), true);
  assert.equal(isCacheablePath(ORIGIN + "/team/reports/new", ORIGIN), true);
  assert.equal(isCacheablePath(ORIGIN + "/reports/", ORIGIN), false);
});

test("SEC-01(ب): /login and /logout are authentication boundaries", () => {
  assert.deepEqual([...AUTH_BOUNDARY_PREFIXES].sort(), ["/login", "/logout"]);
  assert.equal(isAuthBoundaryNavigation(ORIGIN + "/login", ORIGIN), true);
  assert.equal(isAuthBoundaryNavigation(ORIGIN + "/login/quick", ORIGIN), true);
  assert.equal(isAuthBoundaryNavigation(ORIGIN + "/login/language", ORIGIN), true);
  assert.equal(isAuthBoundaryNavigation(ORIGIN + "/logout", ORIGIN), true);
});

test("SEC-01(ب): ordinary pages are not authentication boundaries", () => {
  assert.equal(isAuthBoundaryNavigation(ORIGIN + "/", ORIGIN), false);
  assert.equal(isAuthBoundaryNavigation(ORIGIN + "/team/tasks", ORIGIN), false);
  assert.equal(isAuthBoundaryNavigation(ORIGIN + "/animals/5", ORIGIN), false);
  // مسار يحوي "login" بمنتصفه لا يُعدّ حدّاً — المطابقة على بادئة المسار فقط
  assert.equal(isAuthBoundaryNavigation(ORIGIN + "/animals/login-tag", ORIGIN), false);
});

test("SEC-01(ب): cross-origin or malformed URLs are never auth boundaries, never throw", () => {
  assert.equal(isAuthBoundaryNavigation("https://evil.com/login", ORIGIN), false);
  assert.equal(isAuthBoundaryNavigation("not a url", ORIGIN), false);
});

test("SEC-01(ب): purgeAllCaches deletes every cache, whatever its name", async () => {
  const deleted = [];
  const fakeCaches = {
    keys: () => Promise.resolve(["murabi-offline-v7", "murabi-offline-v8", "anything-else"]),
    delete: (k) => { deleted.push(k); return Promise.resolve(true); },
  };
  await purgeAllCaches(fakeCaches);
  assert.deepEqual(deleted.sort(), ["anything-else", "murabi-offline-v7", "murabi-offline-v8"]);
});

test("SEC-01(ب): purgeAllCaches with no caches → resolves without throwing", async () => {
  const fakeCaches = { keys: () => Promise.resolve([]), delete: () => Promise.resolve(true) };
  await purgeAllCaches(fakeCaches);
});

test("SEC-01(ج): a download response (Content-Disposition: attachment) is never cached", () => {
  const download = {
    ok: true, url: ORIGIN + "/finance/export",
    headers: { get: (h) => (h.toLowerCase() === "content-disposition" ? "attachment; filename=x.xlsx" : null) },
  };
  assert.equal(shouldCacheResponse(download), false);
});

test("SEC-01(ج): an inline (non-attachment) response with headers → still cacheable", () => {
  const page = {
    ok: true, url: ORIGIN + "/animals/5",
    headers: { get: (h) => (h.toLowerCase() === "content-type" ? "text/html; charset=utf-8" : null) },
  };
  assert.equal(shouldCacheResponse(page), true);
});

test("SEC-01: CACHE_NAME was bumped past the leaking v7 (forces purge on every device at activate)", () => {
  const m = /^murabi-offline-v(\d+)$/.exec(CACHE_NAME);
  assert.ok(m, "CACHE_NAME must keep the murabi-offline-vN pattern");
  assert.ok(Number(m[1]) >= 8, "must be >= v8 so the activate handler deletes the contaminated v7 cache");
});

test("SEC-01(ب): endedAtLogin matches the login *path prefix*, not the substring anywhere", () => {
  assert.equal(endedAtLogin({ url: ORIGIN + "/login" }), true);
  assert.equal(endedAtLogin({ url: ORIGIN + "/login?next=%2Fanimals%2F5" }), true);
  assert.equal(endedAtLogin({ url: ORIGIN + "/login/quick" }), true);
  assert.equal(endedAtLogin({ url: ORIGIN + "/animals/5" }), false);
  // "login" بمنتصف المسار أو بالاستعلام فقط ليس صفحة دخول
  assert.equal(endedAtLogin({ url: ORIGIN + "/animals/login-tag" }), false);
  assert.equal(endedAtLogin({ url: ORIGIN + "/animals?q=/login" }), false);
  assert.equal(endedAtLogin(null), false);
  assert.equal(endedAtLogin({ url: "not a url" }), false);
});

// SEC-01: التخزين المسبق عند التثبيت كان cache.add() الأعمى — يخزّن ردّ
// صفحة الدخول تحت مفتاح "/" لو ثُبِّت الإصدار الجديد والمستخدم غير مصادَق.
test("SEC-01: precacheUrls stores a normal page but NEVER a login-redirected response", async () => {
  const stored = [];
  const fakeCache = { put: (url, res) => { stored.push(url); return Promise.resolve(); } };
  const fakeFetch = (url) => Promise.resolve(
    url === "/"
      ? { ok: true, url: ORIGIN + "/login" }          // غير مصادَق → أُعيد توجيهه للدخول
      : { ok: true, url: ORIGIN + url }               // صفحة عادية
  );
  await precacheUrls(fakeCache, ["/", "/team/tasks", "/alerts/mine"], fakeFetch);
  assert.deepEqual(stored.sort(), ["/alerts/mine", "/team/tasks"]);
});

test("SEC-01: precacheUrls tolerates a failing fetch without dropping the rest", async () => {
  const stored = [];
  const fakeCache = { put: (url) => { stored.push(url); return Promise.resolve(); } };
  const fakeFetch = (url) => (url === "/team/tasks" ? Promise.reject(new Error("offline")) : Promise.resolve({ ok: true, url: ORIGIN + url }));
  await precacheUrls(fakeCache, ["/", "/team/tasks"], fakeFetch);
  assert.deepEqual(stored, ["/"]);
});

test("PRECACHE_URLS: every precached url is on the allowlist and is not an auth boundary", () => {
  for (const url of PRECACHE_URLS) {
    assert.equal(isCacheablePath(ORIGIN + url, ORIGIN), true, url);
    assert.equal(isAuthBoundaryNavigation(ORIGIN + url, ORIGIN), false, url);
  }
});

// ============================================================
// SEC-01(د) — حارس الحقبة: ردّ بدأ قبل المسح وتأخّر حتى بعده يجب ألا
// يُعيد بيانات المستخدم السابق لكاش نُظِّف للتو (فجوة القبول رقم 2).
// ============================================================

test("SEC-01(د): purge bumps the epoch, so a captured pre-purge epoch is no longer committable", async () => {
  const startEpoch = currentCacheEpoch();
  assert.equal(mayCommitCache(startEpoch), true, "قبل المسح: يُسمح بالكتابة");
  await purgeAllCaches({ keys: () => Promise.resolve([]), delete: () => Promise.resolve(true) });
  assert.equal(mayCommitCache(startEpoch), false, "بعد المسح: كتابة الطلب القديم مرفوضة");
  // طلب جديد يبدأ بعد المسح يلتقط الحقبة الجديدة ويُسمح له
  const freshEpoch = currentCacheEpoch();
  assert.equal(mayCommitCache(freshEpoch), true);
});

test("SEC-01(د): epoch is monotonic across successive purges", async () => {
  const e0 = currentCacheEpoch();
  const fake = { keys: () => Promise.resolve([]), delete: () => Promise.resolve(true) };
  await purgeAllCaches(fake);
  await purgeAllCaches(fake);
  assert.ok(currentCacheEpoch() >= e0 + 2);
  assert.equal(mayCommitCache(e0), false);
});
