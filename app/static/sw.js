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
 * بعد الخروج. الإصلاح بخمس طبقات مستقلة (أي واحدة تكفي وحدها لسدّ أغلب
 * الطريق، والخمس معاً دفاع بالعمق):
 *   (أ) **قائمة سماح** (allowlist) بدل استثناء بالاسم: لا يُخزَّن أي ردّ
 *       افتراضياً. المسموح **حصراً**: أصول عامة ثابتة غير مرتبطة بأي
 *       مستخدم (/static/). **صفر صفحات HTML** — راجع "لماذا لا صفحات" أدناه.
 *   (ب) أي تنقّل يعبر "حدّ مصادقة" (/login أو /logout) — أو أي ردّ انتهى
 *       بإعادة توجيه لصفحة الدخول (جلسة منتهية) — يمسح **كل** الكاش فوراً
 *       (AUTH_BOUNDARY_PREFIXES + purgeAllCaches). هذا يحسم المشكلة عند
 *       جذرها: لا يمكن أن يصير شخص مستخدماً آخر دون المرور بـ/login.
 *   (ج) أي ردّ تنزيل (Content-Disposition: attachment — تصدير Excel/JSON/
 *       PDF) لا يُخزَّن أبداً (shouldCacheResponse) — دفاع مضاعف فوق (أ).
 *   (د) **حارس الحقبة** (cache epoch): ردّ بدأ طلبه قبل المسح وتأخّر حتى
 *       بعده لا يُعاد للكاش — كل مسح يرفع عدّاد الحقبة، والكتابة تُلغى لو
 *       تغيّرت الحقبة بين بدء الطلب ووصول الردّ (mayCommitCache).
 *   (هـ) **تبليغ حدّ المصادقة**: منع التخزين لا يمحو ما هو **معروض** أصلاً
 *       بتبويب بقي مفتوحاً على صفحة المستخدم السابق. عند أي حدّ مصادقة
 *       يُبلَّغ كل تبويب مفتوح (notifyClientsOfAuthBoundary) فيعيد التحميل
 *       وينتهي لصفحة الدخول. يُستثنى التبويب الواقف على /login (منع حلقة)
 *       و**التبويب المُنتقِل نفسه** (event.clientId) — تبليغه كان يجهض
 *       انتقاله لـ/logout فلا يتم الخروج أصلاً.
 *
 * **لماذا لا صفحات إطلاقاً؟** (مراجعة 2026-09-05 على الدفعة نفسها) — جرّبنا
 * أولاً استثناءً "لصفحات ميدانية آمنة" (الرئيسية، اليوم، تنبيهاتي، المهام،
 * البلاغات) بحجة أنها ضمن صلاحيات أي عضو ميداني. قياس فعلي للردود بين حساب
 * مالك وحساب عامل أسقط الحجّة: **الخمسة كلها** تختلف نصّياً، وتحمل اسم
 * المستخدم، و**رمز CSRF مرتبطاً بالجلسة** بـ<meta name="csrf-token"> وبـ10–11
 * حقلاً مخفياً داخل الفورمات. اشتراك مستخدمَين بصلاحية *فتح* صفحة لا يعني
 * أن *الردّ* آمن للمشاركة: الردّ يحمل هوية الجلسة نفسها. فأي صفحة HTML
 * أُخرجت من الكاش نهائياً بهذي الدفعة.
 *
 * **أثر ذلك على الاستخدام** (مقصود وموثَّق): عرض الصفحات بلا اتصال لم يعد
 * يعمل — فتح التطبيق على جهاز مقطوع الاتصال من الصفر يعطي خطأ المتصفح بدل
 * آخر نسخة مخزَّنة، ولا يمكن الوصول لشاشة إدخال جديدة وأنت أوفلاين. **ما
 * زال يعمل**: أي صفحة مفتوحة أصلاً قبل انقطاع الاتصال تكمل عملها، وطابور
 * الإدخالات (data-offline + IndexedDB) يخزّن ويعيد الإرسال تلقائياً كما هو
 * تماماً — وهو القدرة الميدانية الحرجة. إعادة عرض الصفحات أوفلاين بأمان
 * تحتاج تصميماً مستقلاً (تقسيم الكاش حسب المستخدم أو قشرة ثابتة بلا بيانات)
 * وهي خارج نطاق هذي الدفعة عمداً.
 *
 * ورُفع CACHE_NAME إلى v9 عمداً: معالج activate الموجود أصلاً يمسح أي كاش
 * باسم مختلف، فأول تفعيل للنسخة الجديدة على أي جهاز يمسح الكاش القديم كله.
 * **متى يصبح الإصلاح فعّالاً**: عند تفعيل (activate) الـSW الجديد على
 * الجهاز — يحدث تلقائياً بعد جلب /sw.js المحدَّث (المتصفح يفحصه مع كل
 * تنقّل) بفضل skipWaiting()+clients.claim(). حتى تلك اللحظة قد يخدم الـSW
 * القديم نسخة ملوَّثة واحدة. لضمان فوري على جهاز مشترك بعد النشر:
 * افتح الموقع مرة وأنت متصل (تنقّل واحد يكفي لجلب /sw.js الجديد).
 * **الخروج والدخول وحدهما ليسا دليلاً** أن الجهاز صار على النسخة الجديدة —
 * الـSW القديم ينفّذهما بلا ترقية. الدليل الوحيد: تشغيل
 * tests/e2e/sw_post_deploy_check.js بأدوات المطوّر على الجهاز نفسه ورؤية
 * PASS. (موثَّق بـtests/e2e/README وبسجل التدقيق؛ الأداة نفسها مُختبَرة
 * بسيناريو (E) داخل sw_cache_isolation_e2e.py.)
 *
 * دليل قرار قائمة السماح قابل لإعادة التشغيل:
 * `bash tests/e2e/run_sw_e2e.sh --diff` (tests/e2e/page_response_diff_e2e.py)
 * يقيس فرق الردّ بين حساب مالك وحساب عامل للمسارات الخمسة المذكورة أعلاه.
 */
// v9 (لا v8): منطق حدّ المصادقة تغيّر جوهرياً بعد v8 (مرحلتان: حجب ثم
// إعادة تحميل بعد التأكيد). لو بقي الاسم v8 لكان جهاز يشغّل النسخة
// الوسيطة يُبلِّغ "v8" ويجتاز فحص ما بعد النشر رغم أنه بلا إصلاح الترتيب.
// اسم الكاش هو هوية النسخة على الجهاز، فيتغيّر كلما تغيّر السلوك.
const CACHE_NAME = "murabi-offline-v9";

// كان يخزّن أربع صفحات مسبقاً عند التثبيت. أُفرِغ بـSEC-01: كل صفحة HTML
// تحمل هوية جلسة (اسم المستخدم + رمز CSRF)، فتخزينها المسبق يعني تخزين
// جلسة أول من يفتح التطبيق ثم تقديمها لمن بعده. الأصول الثابتة تُخزَّن
// تلقائياً عند أول زيارة تحتاجها — لا حاجة لقائمة مسبقة.
const PRECACHE_URLS = [];

// SEC-01(أ) — قائمة السماح، بندان:
//
// (1) **المسموح**: أصول عامة ثابتة غير مرتبطة بأي مستخدم — كل شي تحت
//     /static/ (سكربتات، أيقونات، خطوط، manifest). متطابقة لكل المستخدمين
//     فلا تسريب ممكن. ملاحظة: مسح حدّ المصادقة (purgeAllCaches) يمسحها هي
//     أيضاً — مسح شامل بلا استثناء أبسط وأأمن من انتقاء ما يُستبقى، والكلفة
//     إعادة تنزيل أصول ثابتة مرة واحدة بعد كل تسجيل دخول.
function isPublicAsset(pathname) {
  return pathname.startsWith("/static/");
}

// (2) **لا استثناء لأي صفحة HTML.** جرّبنا استثناءً لخمس صفحات ميدانية
//     وأسقطه القياس: كلها تحمل اسم المستخدم ورمز CSRF الخاص بالجلسة
//     (راجع تعليق الرأس). قائمة السماح صارت isPublicAsset وحدها. أي طلب
//     لإضافة صفحة للكاش مستقبلاً يجب أن يثبت أولاً أن **الردّ نفسه** خالٍ
//     من أي بيانات جلسة أو مستخدم، لا أن المستخدمين يشتركون بصلاحية فتحه.

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
// SEC-01(أ): قائمة سماح — يُخزَّن فقط من نفس الأصل، وفقط أصل عام ثابت
// (/static/). كل ما عداه → false، بما فيه **كل** صفحات HTML بلا استثناء.
function isCacheablePath(requestUrl, origin) {
  origin = origin || self.location.origin;
  try {
    var url = new URL(requestUrl);
    if (url.origin !== origin) return false;
    return isPublicAsset(url.pathname);
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

// SEC-01(هـ) — مسح الكاش لا يمحو ما هو **معروض** أصلاً بتبويب مفتوح: تبويب
// بقي على صفحة المالك يظل يعرض بياناته بالـDOM بعد أن يسجّل غيره الدخول.
//
// **الترتيب مهم، ومرحلتان لا واحدة** (تصحيح 2026-09-05 بعد مراجعة): حدث
// fetch لـ/logout يصل **قبل** أن يعالجه الخادم — الجلسة ما زالت مفتوحة
// لحظتها. لو بلّغنا التبويبات "أعيدي التحميل" هنا، لقرأت الصفحات المحمية
// بالجلسة **القديمة** وعرضت بيانات المالك من جديد (طازجة هذي المرة، لا
// مخزَّنة)، ثم لا يصلها شيء بعد اكتمال الخروج فتبقى عارضة لها. فصار:
//
//   1) عند **بدء** التبديل: MURABI_AUTH_BOUNDARY_START ⇒ التبويب يحجب
//      محتواه فوراً بلا أي قراءة للشبكة. لا بيانات للحساب السابق تُعرض
//      من اللحظة الأولى.
//   2) عند **تأكيد اكتمال** التبديل (ظهور العميل الناتج عن التنقّل =
//      الوثيقة الجديدة أُنشئت = الخادم ردّ وطبّق Set-Cookie):
//      MURABI_AUTH_BOUNDARY ⇒ التبويب يعيد التحميل الآن، بجلسة محسومة.
//
// نستثني التبويبات الواقفة على صفحة دخول أصلاً (لا بيانات لديها، ومنعاً
// لحلقة إعادة تحميل)، ونستثني التبويب المُنتقِل نفسه (تحت).
function buildAuthBoundaryStartMessage() {
  return { type: "MURABI_AUTH_BOUNDARY_START" };
}

function buildAuthBoundaryMessage() {
  return { type: "MURABI_AUTH_BOUNDARY" };
}

// `excludeClientId` = التبويب الذي **يقوم** بالتنقّل نفسه (event.clientId).
// استثناؤه ليس تجميلاً: وقت وصول حدث fetch لـ/logout يكون هذا التبويب لسا
// معروضاً على رابطه القديم داخل clients.matchAll، فلو بلّغناه أعاد التحميل
// وأجهض انتقاله الجاري إلى /logout (net::ERR_ABORTED) — فما يتم الخروج
// أصلاً. وهو لا يحتاج التبليغ: انتقاله نفسه ينتهي بصفحة الدخول.
function notifyAuthBoundaryClients(message, matchAllFn, excludeClientId) {
  matchAllFn = matchAllFn || (() => self.clients.matchAll({ type: "window" }));
  return matchAllFn().then((clientList) => {
    clientList.forEach((client) => {
      if (excludeClientId && client.id === excludeClientId) return;
      var onLoginPage = false;
      try { onLoginPage = new URL(client.url).pathname.startsWith("/login"); } catch (e) { }
      if (!onLoginPage) client.postMessage(message);
    });
    return clientList;
  });
}

function notifyClientsOfAuthBoundaryStart(matchAllFn, excludeClientId) {
  return notifyAuthBoundaryClients(buildAuthBoundaryStartMessage(), matchAllFn, excludeClientId);
}

function notifyClientsOfAuthBoundary(matchAllFn, excludeClientId) {
  return notifyAuthBoundaryClients(buildAuthBoundaryMessage(), matchAllFn, excludeClientId);
}

// انتظار **تأكيد** اكتمال حدّ المصادقة قبل السماح بإعادة تحميل أي تبويب.
// الإشارة: ظهور العميل الناتج عن هذا التنقّل (event.resultingClientId).
// المتصفح لا يُظهره بـclients.get إلا بعد أن تُنشأ الوثيقة الجديدة فعلاً —
// أي بعد أن يردّ الخادم ويُطبَّق Set-Cookie. قِيس بـChromium على خادم
// /logout بطيء متعمَّد (1.5 ثانية): الرسالة الأولى عند 2ms، والتأكيد عند
// 1515ms ورابط العميل الناتج /login. فهذي إشارة "بعد الاكتمال" لا تقدير زمني.
// عند غياب resultingClientId نستبدلها بمسح clients بحثاً عن تبويب وصل
// لصفحة الدخول. وعند انتهاء المهلة: **لا نبلّغ إطلاقاً** — الأسوأ أن نأذن
// بإعادة قراءة صفحة محمية قبل التأكيد، وشبكة الأمان بالعميل تتكفّل.
const AUTH_BOUNDARY_SETTLE_BUDGET_MS = 10000;
const AUTH_BOUNDARY_POLL_MS = 100;

function defaultDelay(ms) {
  return new Promise(function (resolve) { setTimeout(resolve, ms); });
}

function waitForAuthBoundaryToSettle(resultingClientId, deps) {
  deps = deps || {};
  var delayFn = deps.delay || defaultDelay;
  var budget = deps.budgetMs === undefined ? AUTH_BOUNDARY_SETTLE_BUDGET_MS : deps.budgetMs;
  var step = deps.pollMs === undefined ? AUTH_BOUNDARY_POLL_MS : deps.pollMs;
  var getClient = deps.getClient || function (id) { return self.clients.get(id); };
  var matchAllFn = deps.matchAll || (() => self.clients.matchAll({ type: "window" }));

  function probe() {
    if (resultingClientId) {
      return Promise.resolve()
        .then(function () { return getClient(resultingClientId); })
        .catch(function () { return undefined; })
        .then(function (client) { return client || null; });
    }
    // لا معرّف ناتج: نبحث عن أي تبويب وصل فعلاً لصفحة الدخول.
    return Promise.resolve()
      .then(matchAllFn)
      .catch(function () { return []; })
      .then(function (list) {
        for (var i = 0; i < (list || []).length; i++) {
          try {
            if (new URL(list[i].url).pathname.startsWith("/login")) return list[i];
          } catch (e) { }
        }
        return null;
      });
  }

  var waited = 0;
  function poll() {
    return probe().then(function (found) {
      if (found) return found;
      waited += step;
      if (waited >= budget) return null;
      return delayFn(step).then(poll);
    });
  }
  return poll();
}

// SEC-01 — تحقّق ما بعد النشر: الجهاز قد يبقى على الـSW القديم بعد النشر،
// والخروج والدخول لا يكشفان ذلك إطلاقاً. أي عميل يستطيع سؤال الـSW **الفعّال
// على هذا الجهاز** عن إصداره؛ نسخة قديمة لا تعرف هذه الرسالة فلا تردّ أصلاً،
// وغياب الرد بحد ذاته دليل أن الجهاز لم يُرقَّ. تُستهلك بـ
// tests/e2e/sw_post_deploy_check.js.
const SW_VERSION_QUERY = "MURABI_SW_VERSION";

function buildVersionReply() {
  return { type: "MURABI_SW_VERSION_RESULT", cacheName: CACHE_NAME };
}

function answerVersionQuery(event) {
  if (!event || !event.data || event.data.type !== SW_VERSION_QUERY) return null;
  var reply = buildVersionReply();
  if (event.ports && event.ports[0]) event.ports[0].postMessage(reply);
  else if (event.source && event.source.postMessage) event.source.postMessage(reply);
  return reply;
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

  self.addEventListener("message", (event) => {
    answerVersionQuery(event);
  });

  self.addEventListener("fetch", (event) => {
    const req = event.request;

    // SEC-01(ب): حدّ مصادقة — يُفحص **قبل** استثناء المسار تحت، لأن
    // /login و/logout مستثنيان من التخزين أصلاً فكانا يمرّان بلا أي تدخّل.
    // لا نجيب نحن عن هذا الطلب (المتصفح يتولاه طبيعياً)، بس نمسح الكاش
    // كاملاً ونمدّ عمر الحدث لين يكتمل المسح فعلياً.
    if (req.mode === "navigate" && isAuthBoundaryNavigation(req.url)) {
      // نمسح، ثم **نحجب** فوراً، ثم ننتظر تأكيد اكتمال الخروج قبل أن نأذن
      // بإعادة التحميل (SEC-01(هـ) — الترتيب مشروح فوق عند الدالتين).
      // التبليغ من هنا فقط — لا من مسار endedAtLogin تحت — منعاً لحلقة
      // إعادة تحميل (إعادة التحميل نفسها تنتهي غالباً بإعادة توجيه للدخول).
      const boundaryClientId = event.clientId;
      const boundaryResultingClientId = event.resultingClientId;
      event.waitUntil(
        purgeAllCaches()
          .then(() => notifyClientsOfAuthBoundaryStart(null, boundaryClientId))
          .then(() => waitForAuthBoundaryToSettle(boundaryResultingClientId))
          .then((settled) => (settled
            ? notifyClientsOfAuthBoundary(null, boundaryClientId)
            : null))
      );
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
    isPublicAsset, currentCacheEpoch, mayCommitCache,
    buildAuthBoundaryMessage, notifyClientsOfAuthBoundary,
    buildAuthBoundaryStartMessage, notifyClientsOfAuthBoundaryStart,
    waitForAuthBoundaryToSettle, AUTH_BOUNDARY_SETTLE_BUDGET_MS, AUTH_BOUNDARY_POLL_MS,
    SW_VERSION_QUERY, buildVersionReply, answerVersionQuery,
  };
}
