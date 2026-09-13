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
    const subscribeResp = await fetch("/push/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
      body: JSON.stringify(subscription.toJSON()),
    });
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

document.addEventListener("DOMContentLoaded", function () {
  const banner = document.querySelector("[data-push-banner]");
  if (!banner || !pushNotificationsSupported()) return;
  if (Notification.permission === "denied") return;

  navigator.serviceWorker.ready.then(function (registration) {
    registration.pushManager.getSubscription().then(function (existing) {
      if (existing) return; // مشترك أصلاً بهذا الجهاز
      banner.style.display = "flex";
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

if (typeof module !== "undefined" && module.exports) {
  module.exports = { urlBase64ToUint8Array, pushNotificationsSupported };
}
