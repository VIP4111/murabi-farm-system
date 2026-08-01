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
const CACHE_NAME = "murabi-offline-v3";

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

function isCacheablePath(requestUrl) {
  try {
    var url = new URL(requestUrl);
    if (url.origin !== self.location.origin) return false;
    return !EXCLUDED_PATH_PREFIXES.some(function (p) { return url.pathname.startsWith(p); });
  } catch (e) {
    return false;
  }
}

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

  event.respondWith(
    fetch(req)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
        return res;
      })
      .catch(() => caches.match(req))
  );
});
