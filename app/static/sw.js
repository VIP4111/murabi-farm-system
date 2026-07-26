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
 * صفحات المسار الثابت (OFFLINE_URLS) تُخزَّن مسبقاً عند تثبيت الـService
 * Worker. صفحات فيها مُعرِّف رقمي بالمسار (تفاصيل رأس، تعديل صنف...) ما
 * يُعرَف مسبقاً — تُطابَق بأنماط (OFFLINE_URL_PATTERNS) وتُخزَّن أول مرة
 * تُفتح وهي متصلة (تخزين انتهازي عادي، نفس فكرة أي PWA).
 */
const CACHE_NAME = "murabi-offline-v2";

const OFFLINE_URLS = [
  "/",
  "/alerts", "/alerts/mine",
  "/animals", "/animals/new", "/animals/bulk-purchase", "/animals/bulk/select", "/animals/smart-sale",
  "/assistant/",
  "/barns", "/barns/new",
  "/batches/", "/batches/new",
  "/climate/", "/climate/settings",
  "/feed/items", "/feed/items/new",
  "/feed/rations", "/feed/rations/new",
  "/feed/barn-plans", "/feed/barn-plans/new",
  "/feed/movements", "/feed/movements/new",
  "/feed/calculator", "/feed/optimizer", "/feed/fcr",
  "/finance/", "/finance/new", "/finance/health", "/finance/monthly-cost-report",
  "/health/vet-visits", "/health/vet-visits/new",
  "/health/diseases", "/health/diseases/new",
  "/health/vaccinations", "/health/vaccinations/new",
  "/health/pharmacy", "/health/pharmacy/new", "/health/pharmacy/shortages",
  "/health/disease-types", "/health/disease-types/new",
  "/health/doctors", "/health/doctors/new",
  "/health/protocols", "/health/protocols/new",
  "/health/injection-guide", "/health/diagnose",
  "/ostrich/eggs", "/ostrich/eggs/new", "/ostrich/incubators", "/ostrich/incubators/new",
  "/repro/matings", "/repro/matings/new",
  "/repro/pregnancies", "/repro/pregnancies/new",
  "/repro/programs", "/repro/programs/new",
  "/repro/sonar", "/repro/sonar/new",
  "/reports/", "/reports/births", "/reports/mortality", "/reports/sales",
  "/settings", "/settings/audit", "/settings/backup",
  "/team/tasks", "/team/tasks/new",
  "/team/members", "/team/members/new",
  "/team/reports", "/team/reports/new",
  "/team/worker/report/health", "/team/worker/report/isolation",
  "/team/worker/report/feed", "/team/worker/report/ostrich",
  "/warehouses/", "/warehouses/new",
];

// صفحات فيها مُعرِّف رقمي بالمسار — تُخزَّن انتهازياً أول ما تُزار وهي متصلة
const OFFLINE_URL_PATTERNS = [
  /^\/animals\/\d+$/,
  /^\/animals\/\d+\/edit$/,
  /^\/animals\/\d+\/workflow$/,
  /^\/barns\/\d+\/edit$/,
  /^\/batches\/\d+$/,
  /^\/feed\/items\/\d+\/edit$/,
  /^\/feed\/rations\/\d+$/,
  /^\/health\/pharmacy\/\d+\/edit$/,
  /^\/health\/protocols\/\d+\/apply$/,
  /^\/ostrich\/eggs\/\d+\/hatch$/,
  /^\/repro\/programs\/\d+$/,
  /^\/repro\/programs\/\d+\/attempts\/new$/,
  /^\/repro\/programs\/\d+\/devices\/new$/,
  /^\/repro\/programs\/\d+\/injections\/new$/,
  /^\/team\/reports\/\d+$/,
  /^\/team\/tasks\/\d+$/,
  /^\/warehouses\/item\/(feed|pharmacy)\/\d+$/,
];

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      Promise.all(OFFLINE_URLS.map((url) => cache.add(url).catch(() => {})))
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

function isOfflineEnabledPath(requestUrl) {
  try {
    var pathname = new URL(requestUrl).pathname;
    if (OFFLINE_URLS.includes(pathname)) return true;
    return OFFLINE_URL_PATTERNS.some(function (re) { return re.test(pathname); });
  } catch (e) {
    return false;
  }
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  // نتدخّل بس بطلبات GET للصفحات المشمولة — أي طلب ثاني (POST، أو صفحة
  // خارج القائمة) يمرّ عادي بدون أي تدخّل من الـService Worker.
  if (req.method !== "GET" || !isOfflineEnabledPath(req.url)) return;

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
