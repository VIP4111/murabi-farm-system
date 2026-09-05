/*
 * Service Worker — تخزين مؤقت لصفحات النظام (بند 53، 2026-07-25: وسِّع من
 * 8 شاشات إدخال ميدانية فقط ليشمل كل الوحدات وكل الأدوار، بما فيها
 * صفحات التفاصيل/التعديل الديناميكية والتقارير القرائية).
 *
 * استراتيجية: شبكة أولاً مع نسخة مخزّنة كبديل عند الفشل (network-first،
 * cache fallback) — عشان المستخدم يشوف دايماً أحدث نسخة لما يكون متصل،
 * ويشتغل من آخر نسخة محفوظة لما ينقطع الاتصال. **تنبيه صادق**: القوائم
 * المنسدلة (الحيوانات، الأدوية...) والتقارير بالصفحة المخزّنة تعكس آخر
 * مرة فُتحت وهو متصل — مو بالضرورة أحدث بيانات لحظياً لو تغيّر شي بعدها.
 *
 * **بند إضافي 82 (2026-08-02) — تغطية أوسع من الصفحات المُزارة مسبقاً
 * (نقطة 8 من قائمة نقاط الضعف)**: قبل هذا البند، أي صفحة ما كانت مذكورة
 * صراحة بـOFFLINE_URLS أو تطابق أحد OFFLINE_URL_PATTERNS تُتجاهَل تماماً
 * من الـService Worker — تعلّق فاضية لو فُتحت أول مرة وأنت أوفلاين، حتى
 * لو زرتها فعلياً وأنت متصل قبل شوي. الحل: قلبنا المنطق من "قائمة سماح"
 * (allowlist) إلى "قائمة استثناء" (denylist) — أي صفحة GET من نفس الموقع
 * تُخزَّن تلقائياً أول ما تُفتح وأنت متصل، ما عدا استثناءات صريحة محدودة
 * (رفع/تنزيل ملفات، تسجيل دخول/خروج). صفر صيانة يدوية لقائمة مسارات
 * مستقبلاً — أي صفحة جديدة تُبنى تدخل التغطية تلقائياً بدون أي تعديل
 * على هذا الملف.
 *
 * **SEC-01 (تدقيق مستقل 2026-09-04 — حاجب إطلاق P0)**: الكاش هنا نطاقه
 * الأصل (origin) لا المستخدم — كاش واحد مفتاحه الرابط فقط، وكان لا يُمسح
 * عند تسجيل الخروج إطلاقاً، ويُقدَّم كلما تأخّرت الشبكة أكثر من
 * NETWORK_TIMEOUT_MS. على لوح/جوال المزرعة المشترك: عامل يدخل بعد المالك
 * كان يشوف صفحات المالك المخزَّنة (المالية، الرواتب، سجل التدقيق) — الطلب
 * ما يوصل السيرفر أصلاً فلا فحص صلاحيات يقع. والأخطر: تفريغ قاعدة البيانات
 * الكامل (/settings/backup/export-now، كان GET) كان يُخزَّن بالكاش ويبقى
 * بعد الخروج. الإصلاح بثلاث طبقات مستقلة (أي واحدة تكفي وحدها لسدّ أغلب
 * الطريق، والثلاث معاً دفاع بالعمق):
 *   (أ) **قائمة سماح** (allowlist) بدل استثناء بالاسم: لا يُخزَّن أي ردّ
 *       افتراضياً. المسموح حصراً: أصول عامة آمنة غير مرتبطة بمستخدم
 *       (/static/)، + استثناء موثَّق مُعزَّل لصفحات العامل الميدانية التي
 *       يحتاجها العمل بلا اتصال (isOfflineFieldPage). أي مسار جديد — بما
 *       فيه أي شاشة محمية أو مرتبطة بمستخدم — لا يُخزَّن حتى يُضاف صراحةً
 *       لقائمة السماح بعد تبرير نطاقه وعزله. راجع OFFLINE_FIELD_PAGE_* أدناه.
 *   (ب) أي تنقّل يعبر "حدّ مصادقة" (/login أو /logout) — أو أي ردّ انتهى
 *       بإعادة توجيه لصفحة الدخول (جلسة منتهية) — يمسح **كل** الكاش فوراً
 *       (AUTH_BOUNDARY_PREFIXES + purgeAllCaches). هذا يحسم المشكلة عند
 *       جذرها: لا يمكن أن يصير شخص مستخدماً آخر دون المرور بـ/login.
 *   (ج) أي ردّ تنزيل (Content-Disposition: attachment — تصدير Excel/JSON/
 *       PDF) لا يُخزَّن أبداً (shouldCacheResponse) — دفاع مضاعف فوق (أ).
 *   (د) **حارس الحقبة** (cache epoch): ردّ بدأ طلبه قبل المسح وتأخّر حتى
 *       بعده لا يُعاد للكاش — كل مسح يرفع عدّاد الحقبة، والكتابة تُلغى لو
 *       تغيّرت الحقبة بين بدء الطلب ووصول الردّ (mayCommitCache).
 * ورُفع CACHE_NAME إلى v8 عمداً: معالج activate الموجود أصلاً يمسح أي كاش
 * باسم مختلف، فأول تفعيل للنسخة الجديدة على أي جهاز يمسح v7 الملوَّث كله.
 * **متى يصبح الإصلاح فعّالاً**: عند تفعيل (activate) الـSW الجديد على
 * الجهاز — يحدث تلقائياً بعد جلب /sw.js المحدَّث (المتصفح يفحصه مع كل
 * تنقّل) بفضل skipWaiting()+clients.claim(). حتى تلك اللحظة قد يخدم الـSW
 * القديم (v7) نسخة ملوَّثة واحدة. لضمان فوري على جهاز مشترك بعد النشر:
 * سجّل خروجاً ودخولاً مرة، أو أغلق كل تبويبات الموقع ثم افتحه. (موثَّق
 * بـtests/e2e/README وبسجل التدقيق.)
 */
const CACHE_NAME = "murabi-offline-v8";

// صفحات القوائم القديمة تبقى مُخزَّنة مسبقاً عند التثبيت (تجربة أول
// استخدام أسرع، قبل حتى ما يزور المستخدم أي صفحة). التخزين الفعلي بعد
// كذا يصير تلقائياً لأي صفحة تُزار (راجع isCacheablePath تحت).
const PRECACHE_URLS = [
  "/", "/team/tasks", "/team/reports", "/alerts/mine",
];

// SEC-01(أ) — قائمة السماح. سياستان:
//
// (1) أصول عامة آمنة غير مرتبطة بأي مستخدم: كل شي تحت /static/ (سكربتات،
//     أيقونات، خطوط، manifest). متطابقة لكل المستخدمين، فلا تسريب ممكن،
//     وتُخزَّن بحرية ولا يمسّها مسح حدّ المصادقة (نُبقيها لسرعة الإقلاع).
function isPublicAsset(pathname) {
  return pathname.startsWith("/static/");
}

// (2) استثناء موثَّق ومُعزَّل: صفحات العامل الميدانية التي يحتاجها العمل
//     بلا اتصال (عرض المهام/البلاغات/التنبيهات/الرئيسية المبسّطة). هذي
//     الصفحات **مرتبطة بمستخدم** (تُعرَض حسب الدور)، فاعتمادها استثناء لا
//     قاعدة — نطاقه وعزله:
//       • النطاق: حصراً المسارات أدناه، وكلها ضمن صلاحيات أي عضو ميداني
//         (لا مالية، لا رواتب، لا إعدادات، لا تقارير تحليلية، لا مساعد).
//       • النظام أحادي المزرعة (مزرعة واحدة لكل نشر)، فلا عزل بين مؤسسات
//         مطلوب؛ الخطر الوحيد هو التبديل بين أدوار نفس المزرعة على الجهاز.
//       • آلية العزل: (ب) مسح الكاش كاملاً عند كل حدّ مصادقة (/login،
//         /logout، أو ردّ أُعيد توجيهه للدخول) + (د) حارس الحقبة للرد
//         المتأخر. فأي صفحة خُزِّنت بجلسة المالك لا تنجو لجلسة العامل —
//         لا يصير أحد مستخدماً آخر دون المرور بـ/login الذي يمسح الكل.
//     أي إضافة لهذي القائمة تتطلب نفس التبرير (نطاق + عزل) قبل اعتمادها.
const OFFLINE_FIELD_PAGE_EXACT = ["/", "/today", "/alerts/mine", "/team/tasks", "/team/reports"];
const OFFLINE_FIELD_PAGE_PREFIXES = ["/team/tasks/", "/team/reports/"];

function isOfflineFieldPage(pathname) {
  if (OFFLINE_FIELD_PAGE_EXACT.indexOf(pathname) !== -1) return true;
  return OFFLINE_FIELD_PAGE_PREFIXES.some(function (p) { return pathname.startsWith(p); });
}

// SEC-01(ب): حدود المصادقة — أي تنقّل (navigate) يبدأ بأحد هذي المسارات
// يعني بالضرورة أن هوية المستخدم على هذا الجهاز تتغيّر أو تُعاد: خروج
// صريح، أو فتح شاشة الدخول (ما يسبق أي دخول بحساب ثانٍ حتماً). عندها
// يُمسح الكاش **كاملاً** قبل أي شي — فالمستخدم التالي يبدأ من كاش فارغ
// ولا يمكن أن يُقدَّم له ردّ مخزَّن من جلسة غيره مهما تأخّرت الشبكة.
// التكلفة: فقدان الكاش الأوفلاين عند تسجيل الدخول فقط (نادر — الجلسة
// طويلة الأمد بـremember=True) وليس أثناء يوم العمل العادي.
const AUTH_BOUNDARY_PREFIXES = ["/login", "/logout"];

function isAuthBoundaryNavigation(requestUrl, origin) {
  origin = origin || self.location.origin;
  try {
    var url = new URL(requestUrl);
    if (url.origin !== origin) return false;
    return AUTH_BOUNDARY_PREFIXES.some(function (p) { return url.pathname.startsWith(p); });
  } catch (e) {
    return false;
  }
}

// SEC-01(د): حارس الحقبة (cache epoch). عدّاد وحيد بمدى الـSW يُرفع مع كل
// مسح كاش. كل طلب يلتقط الحقبة عند بدئه، ولا يُسمح بكتابة رده للكاش إلا لو
// بقيت الحقبة نفسها عند وصوله — فردّ بدأ بجلسة المالك وتأخّر حتى بعد الخروج
// (الذي مسح الكاش ورفع الحقبة) لا يُعيد بيانات المالك لكاش نُظِّف للتو.
var _cacheEpoch = 0;
function currentCacheEpoch() { return _cacheEpoch; }
function mayCommitCache(capturedEpoch) { return capturedEpoch === _cacheEpoch; }

// يمسح كل الكاشات بهذا الأصل بغض النظر عن أسمائها (يشمل أي إصدار قديم
// لم يُنظَّف بعد) ويرفع الحقبة أولاً — فأي كتابة لطلب سابق تُلغى فوراً.
// `cachesApi` وسيط اختياري للاختبار بـNode.js فقط — بالمتصفح الفعلي
// يُستدعى دائماً بلا وسيط فيستخدم `caches` العالمي.
function purgeAllCaches(cachesApi) {
  cachesApi = cachesApi || caches;
  _cacheEpoch++;
  return cachesApi.keys().then(function (keys) {
    return Promise.all(keys.map(function (k) { return cachesApi.delete(k); }));
  });
}

// حد أقصى لعدد الصفحات المخزَّنة (بند إضافي 91، نقطة 7 من التحليل
// الثاني — نقد ذاتي على بند 82) — قبل هذا البند، كل صفحة GET من نفس
// الموقع كانت تُضاف للكاش بلا أي حد أقصى، والتنظيف الوحيد كان مسح
// كامل عند تغيير CACHE_NAME يدوياً. مع مرور الوقت (شاشات تفاصيل
// حيوان/تقرير كثيرة، كل وحدة برقم مختلف بالمسار) الكاش يكبر بلا
// نهاية. Cache API ما فيها انتهاء صلاحية مدمج، فهذا تقليم بسيط أقرب
// لـFIFO: لو تجاوز العدد الحد، نحذف الأقدم (أول المُدخَلين حسب ترتيب
// keys()) لين نرجع تحت الحد.
const MAX_CACHE_ENTRIES = 150;

// دالة صرفة قابلة للاختبار بـNode.js (نفس نمط isCacheablePath) —
// تاخذ قائمة روابط الكاش الحالية وترجّع اللي لازم يُحذَف بس.
function keysToEvict(cachedUrls, maxEntries) {
  if (cachedUrls.length <= maxEntries) return [];
  return cachedUrls.slice(0, cachedUrls.length - maxEntries);
}

function trimCache(cache) {
  return cache.keys().then(function (requests) {
    var urls = requests.map(function (r) { return r.url; });
    var evict = keysToEvict(urls, MAX_CACHE_ENTRIES);
    return Promise.all(evict.map(function (url) { return cache.delete(url); }));
  });
}

// origin كوسيط اختياري (بند إضافي 83 — اختبارات آلية على الجافاسكربت،
// نقطة 9 من قائمة نقاط الضعف) — يخلي الدالة قابلة للاختبار بـNode.js
// خارج بيئة Service Worker الحقيقية بدون محاكاة `self` كاملة. بالمتصفح
// الفعلي دايماً تُستدعى بدون هذا الوسيط، فترجع لنفس السلوك القديم بالضبط.
// SEC-01(أ): قائمة سماح — يُخزَّن فقط من نفس الأصل، وفقط أصل عام آمن أو
// صفحة عامل ميدانية بقائمة الاستثناء الموثَّقة. كل ما عداه → false (لا
// يُخزَّن افتراضياً)، فأي مسار محمي/مرتبط بمستخدم غير مُدرَج لا يُخزَّن.
function isCacheablePath(requestUrl, origin) {
  origin = origin || self.location.origin;
  try {
    var url = new URL(requestUrl);
    if (url.origin !== origin) return false;
    return isPublicAsset(url.pathname) || isOfflineFieldPage(url.pathname);
  } catch (e) {
    return false;
  }
}

// مهلة الشبكة (بند إضافي 201) — قبل هذا البند ما كان فيه أي حد أقصى
// لانتظار fetch()، وعلى iOS Safari تحديداً fetch() لطلب فعلاً ميت (لا
// يوجد اتصال إطلاقاً، مو خطأ سيرفر) ممكن يعلّق لثواني طويلة قبل ما
// يرفض الوعد — يعني fallback الكاش تحت ما يوصله دوره أبداً بوقت
// معقول، والمستخدم يشوف "تحميل" بلا نهاية بدل النسخة المخزَّنة اللي
// كانت جاهزة أصلاً. الحل: سباق (race) بين fetch() ومهلة قصيرة — أول
// واحد يخلص يفوز. دالة صرفة خارج حارس `self` (بند إضافي 83، نفس نمط
// isCacheablePath/keysToEvict) عشان تصير قابلة للاختبار بـNode.js.
const NETWORK_TIMEOUT_MS = 4000;

function raceNetworkWithTimeout(networkPromise, ms, timeoutFn) {
  timeoutFn = timeoutFn || function (delay) {
    return new Promise((resolve) => setTimeout(() => resolve(null), delay));
  };
  return Promise.race([networkPromise, timeoutFn(ms)]);
}

// إصلاح — بلاغ مستخدم حقيقي: "حفظت الحيوان وسوا لي خروج" + "لو سويت
// خروج يرجعني للرئيسية، ما يسوي خروج فعلياً". السبب: كنا نخزّن أي رد
// ناجح لأي رابط بدون فحص وش هو فعلياً. لو صار مرة (جلسة منتهية، تسجيل
// دخول لسا ما تم...) إن رابط داخلي زي "/animals/5" رجع فعلياً صفحة
// تسجيل الدخول (بعد إعادة توجيه الخادم)، كانت تُخزَّن تحت مفتاح
// "/animals/5" نفسه — وبعدين حتى بعد ما تسجّل دخول صح من جديد، أي مرة
// الشبكة تتأخر أكثر من `NETWORK_TIMEOUT_MS` (وارد جداً بنت إنترنت ضعيف)،
// تُعرض نسخة تسجيل الدخول القديمة المخزَّنة بالغلط بدل الصفحة الحقيقية
// — يبان وكإنه "طلع من حسابه" رغم إن جلسته سليمة فعلياً والسيرفر ما شاف
// هذا الطلب أصلاً. الحل: أي رد انتهى فعلياً بصفحة تسجيل الدخول ما
// يُخزَّن إطلاقاً — يُعرض هذي المرة بس، بدون ما يلوّث الكاش لبقية
// الزيارات. دالة صرفة (نفس نمط isCacheablePath/keysToEvict) عشان تصير
// قابلة للاختبار بـNode.js.
// ردّ انتهى فعلياً بصفحة تسجيل الدخول (بعد إعادة توجيه الخادم) — جلسة
// منتهية أو غير مصادَقة. المطابقة على **بادئة المسار** (لا نصّ فرعي بأي
// موضع بالرابط) اتساقاً مع isAuthBoundaryNavigation.
function endedAtLogin(res) {
  if (!res || !res.url) return false;
  try {
    return new URL(res.url).pathname.startsWith("/login");
  } catch (e) {
    return false;
  }
}

function shouldCacheResponse(res) {
  if (!res || !res.ok) return false;
  if (endedAtLogin(res)) return false;
  // SEC-01(ج): أي ردّ تنزيل (تصدير Excel/JSON/PDF، نسخة احتياطية) لا
  // يُخزَّن أبداً — لا قيمة له أوفلاين، وقد يحوي أخطر بيانات النظام.
  // `res.headers` قد تكون غائبة بكائنات الاختبار المبسَّطة — نتعامل معها بأمان.
  if (res.headers && typeof res.headers.get === "function") {
    var disposition = res.headers.get("Content-Disposition") || "";
    if (disposition.toLowerCase().indexOf("attachment") !== -1) return false;
  }
  return true;
}

// إصلاح — بلاغ مستخدم حقيقي: "احفظ بيانات حيوان، والبيانات ما ترتفع
// بنفس اللحظة — بس لو سويت خروج ودخول ترجع صحيحة". السبب مباشر متعلّق
// بنفس آلية السباق فوق: لو الشبكة أبطأ من `NETWORK_TIMEOUT_MS` (وارد
// بنت المزرعة الضعيف)، الصفحة تُعرض من النسخة المخزَّنة القديمة (قبل
// الحفظ)، والرد الفعلي الطازج يوصل بالخلفية بعدها بثوانٍ بدون ما يشوفه
// المستخدم إطلاقاً إلا لو حدّث الصفحة يدوياً. الحل: أي مرة نضطر نعرض
// نسخة مخزَّنة (لأن الشبكة تأخرت)، لما الرد الطازج يوصل فعلاً بالخلفية
// نبعت رسالة لكل تبويب مفتوح على نفس الرابط يطلب منه يعيد التحميل —
// فالمستخدم يشوف بياناته المحفوظة فعلياً خلال ثوانٍ قليلة تلقائياً،
// بدل ما يبقى شايف نسخة قديمة لين يحدّث يدوياً بنفسه.
function buildStaleReloadMessage(url) {
  return { type: "MURABI_STALE_PAGE_REFRESHED", url: url };
}

function notifyClientsOfFreshData(url, matchAllFn) {
  matchAllFn = matchAllFn || (() => self.clients.matchAll({ type: "window" }));
  return matchAllFn().then((clientList) => {
    clientList.forEach((client) => client.postMessage(buildStaleReloadMessage(url)));
    return clientList;
  });
}

// SEC-01: التخزين المسبق عند التثبيت كان `cache.add(url)` مباشرة — يتجاوز
// shouldCacheResponse كلياً. المتصفح يفحص تحديث الـService Worker بأي تنقّل
// (بما فيه /login بعد الخروج)، فلو ثُبِّت إصدار جديد والمستخدم غير مصادَق،
// كان يخزّن ردّ صفحة الدخول تحت مفتاح "/" — نفس فئة الخلل المُصلَح سابقاً
// بـshouldCacheResponse. صار التخزين المسبق يمرّ بنفس القاعدة تماماً. فشل
// أي رابط لا يُسقط الباقي (نفس تسامح cache.add().catch السابق).
// `fetchFn` وسيط اختياري للاختبار بـNode.js فقط.
function precacheUrls(cache, urls, fetchFn) {
  fetchFn = fetchFn || fetch;
  return Promise.all(urls.map(function (url) {
    return Promise.resolve()
      .then(function () { return fetchFn(url); })
      .then(function (res) {
        if (shouldCacheResponse(res)) return cache.put(url, res);
        return null;
      })
      .catch(function () { return null; });
  }));
}

// تسجيل الأحداث محصور ببيئة Service Worker حقيقية بس (بند إضافي 83) —
// `self.addEventListener` غير موجود بـNode.js، وهذا الشرط يخلي نفس
// الملف قابل لـ`require()` وقت الاختبار بدون أي خطأ عند التحميل.
if (typeof self !== "undefined" && typeof self.addEventListener === "function") {
  self.addEventListener("install", (event) => {
    self.skipWaiting();
    event.waitUntil(caches.open(CACHE_NAME).then((cache) => precacheUrls(cache, PRECACHE_URLS)));
  });

  self.addEventListener("activate", (event) => {
    event.waitUntil(
      caches
        .keys()
        .then((keys) => Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))))
        .then(() => self.clients.claim())
    );
  });

  self.addEventListener("fetch", (event) => {
    const req = event.request;

    // SEC-01(ب): حدّ مصادقة — يُفحص **قبل** استثناء المسار تحت، لأن
    // /login و/logout مستثنيان من التخزين أصلاً فكانا يمرّان بلا أي تدخّل.
    // لا نجيب نحن عن هذا الطلب (المتصفح يتولاه طبيعياً)، بس نمسح الكاش
    // كاملاً ونمدّ عمر الحدث لين يكتمل المسح فعلياً.
    if (req.mode === "navigate" && isAuthBoundaryNavigation(req.url)) {
      event.waitUntil(purgeAllCaches());
      return;
    }

    // نتدخّل بس بطلبات GET من نفس الموقع، ما عدا الاستثناءات أعلاه — أي
    // طلب ثاني (POST، أو ملف مرفوع، أو دخول/خروج) يمرّ عادي بدون أي تدخّل.
    if (req.method !== "GET" || !isCacheablePath(req.url)) return;

    // SEC-01(د): حقبة هذا الطلب — تُلتقط عند بدئه، وتُفحص قبل أي كتابة.
    const reqEpoch = currentCacheEpoch();
    const networkFetch = fetch(req)
      .then((res) => {
        // SEC-01(ب): ردّ انتهى بإعادة توجيه لصفحة الدخول = الجلسة انتهت
        // (أو أُنهيت من جهاز ثانٍ). هذا حدّ مصادقة أيضاً وإن لم يمرّ
        // التنقّل بـ/login مباشرة — نمسح الكاش كاملاً قبل تسليم الردّ،
        // فأي دخول لاحق على هذا الجهاز يبدأ من صفر.
        if (endedAtLogin(res)) {
          return purgeAllCaches().then(() => res);
        }
        // SEC-01(د): لا نكتب إلا لو لم يقع مسح بين بدء الطلب ووصول الردّ —
        // يمنع رداً متأخراً من جلسة سابقة أن يعيد بياناتها لكاش نُظِّف للتو.
        if (mayCommitCache(reqEpoch) && shouldCacheResponse(res)) {
          const copy = res.clone();
          caches.open(CACHE_NAME).then((cache) => {
            if (!mayCommitCache(reqEpoch)) return null;  // فحص ثانٍ: قد يقع المسح أثناء فتح الكاش
            return cache.put(req, copy).then(() => trimCache(cache));
          });
        }
        return res;
      })
      .catch(() => null);

    event.respondWith(
      raceNetworkWithTimeout(networkFetch, NETWORK_TIMEOUT_MS).then((res) => {
        if (res) return res;
        // لا رد من الشبكة خلال المهلة (أو فشلت) — النسخة المخزَّنة أول
        // شي، وإلا نترك networkFetch يكمل بالخلفية (ممكن يوصل متأخر
        // ويحدّث الكاش لمرة قادمة حتى لو ما استفدنا منه الآن).
        return caches.match(req).then((cached) => {
          if (cached && req.mode === "navigate") {
            // الرد الطازج لسا بالطريق بالخلفية — لما يوصل فعلاً، نبلّغ
            // أي تبويب مفتوح على نفس الرابط يحدّث نفسه تلقائياً.
            networkFetch.then((freshRes) => {
              if (freshRes) notifyClientsOfFreshData(req.url);
            });
          }
          return cached || networkFetch;
        });
      })
    );
  });
}

// تصدير للاختبار بـNode.js (بند إضافي 83) — بلا أثر بالمتصفح الفعلي،
// `module` غير معرَّف هناك فهذا الشرط ما يتنفَّذ إطلاقاً وقت التشغيل الحي.
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    isCacheablePath, keysToEvict, MAX_CACHE_ENTRIES,
    raceNetworkWithTimeout, NETWORK_TIMEOUT_MS, shouldCacheResponse,
    buildStaleReloadMessage, notifyClientsOfFreshData,
    CACHE_NAME, AUTH_BOUNDARY_PREFIXES, isAuthBoundaryNavigation, purgeAllCaches, endedAtLogin,
    precacheUrls, PRECACHE_URLS,
    isPublicAsset, isOfflineFieldPage, OFFLINE_FIELD_PAGE_EXACT, OFFLINE_FIELD_PAGE_PREFIXES,
    currentCacheEpoch, mayCommitCache,
  };
}
