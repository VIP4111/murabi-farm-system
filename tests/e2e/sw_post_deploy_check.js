/*
 * SEC-01 — تحقّق ما بعد النشر: هل هذا الجهاز يعمل فعلاً بالإصدار الجديد،
 * وهل اختفى الكاش القديم؟
 *
 * الاستعمال: افتح التطبيق بالمتصفح (وأنت مسجّل دخول)، ثم افتح أدوات المطوّر
 * (F12 → Console) والصق هذا الملف كاملاً واضغط Enter. يطبع PASS/FAIL بسبب
 * واضح لكل بند.
 *
 * **لماذا لا يكفي "سجّلت خروجاً ودخولاً"**: الـService Worker القديم ينفّذ
 * الخروج والدخول بشكل طبيعي تماماً بلا أي ترقية، فالمستخدم يرى نفس السلوك
 * ولا يتغيّر شيء. الفحص الأول هنا يسأل الـSW **العامل فعلاً على هذا الجهاز**
 * عن إصداره؛ نسخة قديمة لا تعرف هذه الرسالة فلا تردّ، فيظهر FAIL صريح.
 *
 * يعمل بنسخه واللصق كما هو؛ ويُستخدم أيضاً آلياً بـtests/e2e/sw_cache_isolation_e2e.py
 */
(async function murabiPostDeployCheck() {
  const EXPECTED_CACHE = "murabi-offline-v8";
  const out = { checks: [], pass: true };
  const add = (ok, label, detail) => {
    out.checks.push({ ok, label, detail });
    if (!ok) out.pass = false;
  };

  // 1) Service Worker مسجَّل ونشط
  const reg = await navigator.serviceWorker.getRegistration();
  const active = reg && reg.active;
  add(!!active, "Service Worker نشط", active ? active.scriptURL : "غير مسجَّل");

  // 1ب) **الفحص الحاسم**: نسأل الـSW المسيطر على هذه الصفحة عن إصداره هو.
  // بقية الفحوص تستنتج (اسم الكاش، ما يقدّمه الخادم)؛ هذا يسأل ما يعمل
  // فعلاً على الجهاز. نسخة قديمة لا تعرف هذه الرسالة فلا تردّ، وغياب الرد
  // نفسه دليل أن الجهاز لم يُرقَّ — وهو ما لا يكشفه خروج ودخول إطلاقاً.
  const activeVersion = await new Promise((resolve) => {
    const ctrl = navigator.serviceWorker.controller;
    if (!ctrl) return resolve(null);
    const ch = new MessageChannel();
    const timer = setTimeout(() => resolve(null), 3000);
    ch.port1.onmessage = (e) => {
      clearTimeout(timer);
      resolve(e.data && e.data.cacheName);
    };
    ctrl.postMessage({ type: "MURABI_SW_VERSION" }, [ch.port2]);
  });
  add(activeVersion === EXPECTED_CACHE,
      "الـService Worker العامل على هذا الجهاز هو " + EXPECTED_CACHE,
      activeVersion || "لا ردّ — إصدار قديم لا يعرف رسالة الإصدار");

  // 2) الملف المُقدَّم من الخادم يحمل الإصدار الجديد وطبقاته
  let sw = "";
  try { sw = await (await fetch("/sw.js", { cache: "no-store" })).text(); } catch (e) { }
  add(sw.indexOf('"' + EXPECTED_CACHE + '"') !== -1,
      "الخادم يقدّم " + EXPECTED_CACHE + " (النشر تم)",
      (sw.match(/murabi-offline-v\d+/) || ["?"])[0]);
  for (const marker of ["purgeAllCaches", "mayCommitCache", "notifyClientsOfAuthBoundary"]) {
    add(sw.indexOf(marker) !== -1, "طبقة الحماية موجودة: " + marker, "");
  }

  // 3) لا كاش قديم باقٍ على هذا الجهاز
  const names = await caches.keys();
  const stale = names.filter((n) => n !== EXPECTED_CACHE);
  add(stale.length === 0, "لا كاش قديم على الجهاز", stale.join(", ") || "لا شيء");

  // 4) لا صفحة HTML مخزَّنة (الأصول الثابتة فقط)
  const pages = [];
  for (const n of names) {
    const keys = await (await caches.open(n)).keys();
    for (const r of keys) {
      const p = new URL(r.url).pathname;
      if (!p.startsWith("/static/")) pages.push(n + " → " + p);
    }
  }
  add(pages.length === 0, "لا صفحة مخزَّنة بالكاش (أصول /static/ فقط)",
      pages.join(", ") || "لا شيء");

  const line = (c) => (c.ok ? "✅" : "❌") + " " + c.label + (c.detail ? " — " + c.detail : "");
  console.log("=== فحص SEC-01 بعد النشر ===\n" + out.checks.map(line).join("\n"));
  console.log(out.pass
    ? "\nPASS ✅ — الجهاز يعمل بالإصدار الجديد ولا كاش قديم ولا صفحات مخزَّنة."
    : "\nFAIL ❌ — راجع البنود الحمراء أعلاه. إن كان الإصدار قديماً: أغلق كل "
      + "تبويبات الموقع ثم افتحه وأنت متصل، وأعد الفحص.");
  return out;
})();
