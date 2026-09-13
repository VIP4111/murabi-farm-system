/*
 * إشعارات Push (بند إضافي، طلبك الصريح: "ابيك تصير مثل الواتساب...
 * يجيني تنبيه والجوال بجيبي") — يعرض شريط تفعيل بسيط لأي مستخدم
 * مسجّل دخول، لو متصفحه يدعم Web Push ولسا ما فعّل هذا الجهاز.
 *
 * دوال صرفة (urlBase64ToUint8Array) منفصلة عن التفاعل مع DOM/الشبكة
 * عشان تصير قابلة للاختبار بـNode.js (نفس نمط sw.js).
 */
"use strict";

// applicationServerKey لازم يوصل كـUint8Array خام، بس المفتاح يوصل من
// الخادم كنص Base64URL (نفس تنسيق VAPID_PUBLIC_KEY_B64URL) — تحويل
// قياسي موثَّق بمواصفة Web Push، بدون أي مكتبة خارجية.
function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; i++) outputArray[i] = rawData.charCodeAt(i);
  return outputArray;
}

// إصلاح — بلاغ مستخدم حقيقي: بعد ما غيّرنا مفاتيح VAPID (بسبب خلل
// صيغة سابق)، أي جهاز كان مشترك بالمفتاح القديم صار يفشل بخطأ
// "VapidPkHashMismatch" من خادم الدفع (Google/Mozilla) — الاشتراك
// نفسه مربوط تشفيرياً بالمفتاح العام اللي استُخدم وقت الاشتراك، ما
// يتغيّر تلقائياً لو الخادم غيّر مفاتيحه بعدين. دالة صرفة تقارن مفتاح
// الاشتراك المحلي الحالي بالمفتاح العام الحالي من الخادم — أي فرق
// يعني لازم إلغاء الاشتراك القديم واشتراك جديد بالمفتاح الصحيح.
function arrayBufferToBase64Url(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function pushNotificationsSupported() {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

// إصلاح — بلاغ مباشر أثناء الاختبار الحي: "صار خطأ أثناء الإرسال" مكان
// رسالة واضحة، اتضح إن Flask-WTF (بند إضافي 93 — حماية CSRF بكل فورم
// بالمشروع) يرفض أي POST بلا رمز CSRF بـ400 "The CSRF token is
// missing" — كل فورم عادي بالمشروع يحمل حقل مخفي `csrf_token`، لكن
// طلبات fetch() هذي JSON خالص بدون فورم. الحل القياسي: رمز الصفحة
// نفسها موجود بالفعل بـ`<meta name="csrf-token">` (base.html)، يُرسَل
// كترويسة X-CSRFToken — نفس ما تتوقعه Flask-WTF افتراضياً.
function csrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute("content") : "";
}

function syncSubscriptionWithServer(subscription) {
  return fetch("/push/subscribe", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
    body: JSON.stringify(subscription.toJSON()),
  });
}

async function enablePushNotifications(banner) {
  const btn = banner.querySelector("[data-push-enable-btn]");
  const statusEl = banner.querySelector("[data-push-status]");
  try {
    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      statusEl.textContent = window.PUSH_DENIED_MESSAGE || "";
      return;
    }
    const keyResp = await fetch("/push/vapid-public-key");
    if (!keyResp.ok) {
      statusEl.textContent = window.PUSH_NOT_CONFIGURED_MESSAGE || "";
      return;
    }
    const { public_key } = await keyResp.json();
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(public_key),
    });
    // إصلاح — بلاغ مستخدم حقيقي: "فعّلته واختفى، ونفس إرساله تطلع [ما
    // فيه اشتراك]". السبب: هذا الطلب ما كان يتحقق من نجاحه إطلاقاً —
    // الشريط كان يختفي (يبان كإنه نجح) حتى لو فشل حفظ الاشتراك بالخادم
    // (خطأ سيرفر، انقطاع شبكة لحظي...)، فالمستخدم يفتكر إنه مفعّل
    // وهو فعلياً غير مسجَّل. الآن نتحقق من `response.ok` قبل إخفاء
    // الشريط — فشل الحفظ يبقي الشريط ظاهراً مع رسالة خطأ واضحة بدل
    // نجاح وهمي صامت.
    const subscribeResp = await syncSubscriptionWithServer(subscription);
    if (!subscribeResp.ok) {
      statusEl.textContent = window.PUSH_ERROR_MESSAGE || "";
      return;
    }
    banner.style.display = "none";
    try { localStorage.setItem("murabi_push_enabled", "1"); } catch (e) {}
  } catch (e) {
    statusEl.textContent = window.PUSH_ERROR_MESSAGE || "";
  }
}

// محصور ببيئة متصفح حقيقية بس (نفس نمط sw.js) — يخلي هذا الملف قابل
// لـ`require()` وقت اختبارات Node.js للدوال الصرفة فوق، بدون خطأ
// "document is not defined" عند التحميل.
if (typeof document !== "undefined" && typeof document.addEventListener === "function") {
document.addEventListener("DOMContentLoaded", function () {
  const banner = document.querySelector("[data-push-banner]");
  if (!banner || !pushNotificationsSupported()) return;
  if (Notification.permission === "denied") return;

  // إصلاح — بلاغ مستخدم حقيقي: "ما طلعت لي تنبيه يطلب التفعيل" —
  // بعد محاولة سابقة فشل فيها حفظ الاشتراك بالخادم (خلل الـCSRF
  // المُصلَح سابقاً)، المتصفح نفسه كان يحمل اشتراك محلي فعلي (created
  // بنجاح بجهة المتصفح) رغم إن الخادم ما سجّله إطلاقاً — فـ`getSubscription()`
  // ترجّع اشتراكاً "موجوداً"، والشريط يختفي للأبد بدون ما يعيد المحاولة
  // ولا يعطي المستخدم أي طريقة يرجّعه. الحل: أي اشتراك محلي موجود
  // يُعاد مزامنته مع الخادم بصمت أول ما تفتح الصفحة (idempotent —
  // نفس endpoint يحدّث الصف بدل تكراره) — لو المزامنة نجحت، الشريط
  // يبقى مخفياً (الحالة سليمة فعلاً). لو فشلت، الشريط يطلع من جديد
  // عشان المستخدم يقدر يعيد المحاولة، بدل ما يبقى عالقاً بصمت.
  navigator.serviceWorker.ready.then(function (registration) {
    registration.pushManager.getSubscription().then(function (existing) {
      if (!existing) {
        banner.style.display = "flex";
        return;
      }
      // إصلاح — بلاغ مستخدم حقيقي بعد تغيير مفاتيح VAPID: اشتراك
      // بالمفتاح القديم يفشل بصمت بخطأ "VapidPkHashMismatch" عند كل
      // إرسال، وSyncSubscriptionWithServer العادي ما يكتشف هذا —
      // بيحفظه بنجاح بالخادم لأنه بس يخزّن القيم، ما يتحقق من تطابق
      // المفتاح. نقارن هنا صراحة قبل المزامنة: لو المفتاح تغيّر،
      // نلغي الاشتراك القديم ونطلع الشريط من جديد عشان يشترك بالمفتاح
      // الصحيح الحالي.
      fetch("/push/vapid-public-key").then(function (keyResp) {
        if (!keyResp.ok) { banner.style.display = "flex"; return; }
        keyResp.json().then(function (data) {
          const currentKey = arrayBufferToBase64Url(existing.options.applicationServerKey);
          if (currentKey !== data.public_key) {
            existing.unsubscribe().finally(function () { banner.style.display = "flex"; });
            return;
          }
          syncSubscriptionWithServer(existing).then(function (resp) {
            if (!resp.ok) banner.style.display = "flex";
          }).catch(function () { banner.style.display = "flex"; });
        });
      }).catch(function () { banner.style.display = "flex"; });
    });
  });

  const btn = banner.querySelector("[data-push-enable-btn]");
  if (btn) btn.addEventListener("click", function () { enablePushNotifications(banner); });
  const dismissBtn = banner.querySelector("[data-push-dismiss-btn]");
  if (dismissBtn) {
    dismissBtn.addEventListener("click", function () {
      banner.style.display = "none";
      try { sessionStorage.setItem("murabi_push_banner_dismissed", "1"); } catch (e) {}
    });
  }
  try {
    if (sessionStorage.getItem("murabi_push_banner_dismissed") === "1") banner.style.display = "none";
  } catch (e) {}
});
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { urlBase64ToUint8Array, pushNotificationsSupported, arrayBufferToBase64Url };
}
