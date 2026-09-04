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
 */
const CACHE_NAME = "murabi-offline-v7";

// صفحات القوائم القديمة تبقى مُخزَّنة مسبقاً عند التثبيت (تجربة أول
// استخدام أسرع، قبل حتى ما يزور المستخدم أي صفحة). التخزين الفعلي بعد
// كذا يصير تلقائياً لأي صفحة تُزار (راجع isCacheablePath تحت).
const PRECACHE_URLS = [
  "/", "/team/tasks", "/team/reports", "/alerts/mine",
];

// مسارات مستثناة صراحة من التخزين المؤقت — ملفات مرفوعة (قد تكون كبيرة،
// وتخزينها أوفلاين ما يفيد لأنها أصلاً ثابتة بعد الرفع)، وصفحات الدخول/
// الخروج (تخزينها بلا فائدة — ما تقدر تسجّل دخول فعلي وأنت أوفلاين).
const EXCLUDED_PATH_PREFIXES = ["/uploads/", "/login", "/logout"];

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
function isCacheablePath(requestUrl, origin) {
  origin = origin || self.location.origin;
  try {
    var url = new URL(requestUrl);
    if (url.origin !== origin) return false;
    return !EXCLUDED_PATH_PREFIXES.some(function (p) { return url.pathname.startsWith(p); });
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
function shouldCacheResponse(res) {
  if (!res || !res.ok) return false;
  return res.url.indexOf("/login") === -1;
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

// تسجيل الأحداث محصور ببيئة Service Worker حقيقية بس (بند إضافي 83) —
// `self.addEventListener` غير موجود بـNode.js، وهذا الشرط يخلي نفس
// الملف قابل لـ`require()` وقت الاختبار بدون أي خطأ عند التحميل.
if (typeof self !== "undefined" && typeof self.addEventListener === "function") {
  self.addEventListener("install", (event) => {
    self.skipWaiting();
    event.waitUntil(
      caches.open(CACHE_NAME).then((cache) =>
        Promise.all(PRECACHE_URLS.map((url) => cache.add(url).catch(() => {})))
      )
    );
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
    // نتدخّل بس بطلبات GET من نفس الموقع، ما عدا الاستثناءات أعلاه — أي
    // طلب ثاني (POST، أو ملف مرفوع، أو دخول/خروج) يمرّ عادي بدون أي تدخّل.
    if (req.method !== "GET" || !isCacheablePath(req.url)) return;

    const networkFetch = fetch(req)
      .then((res) => {
        if (shouldCacheResponse(res)) {
          const copy = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, copy).then(() => trimCache(cache)));
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
    isCacheablePath, EXCLUDED_PATH_PREFIXES, keysToEvict, MAX_CACHE_ENTRIES,
    raceNetworkWithTimeout, NETWORK_TIMEOUT_MS, shouldCacheResponse,
    buildStaleReloadMessage, notifyClientsOfFreshData,
  };
}
