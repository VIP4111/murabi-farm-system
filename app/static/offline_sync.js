/*
 * طابور المزامنة المحلي (IndexedDB) — يشتغل لأي <form data-offline> بأي
 * صفحة. من بند 53 (2026-07-25) صار مفعَّلاً لكل الأدوار وكل شاشات
 * التسجيل الفردي والعمليات الجماعية والمالية، مو بس الثمانية الأصلية.
 *
 * الفكرة: لو الاتصال متوفر، الفورم يُرسَل عادي بدون أي تدخّل (سلوك
 * المتصفح الطبيعي، صفر تغيير عن قبل). لو مقطوع، نمنع الإرسال الطبيعي،
 * نخزّن كل حقول الفورم (نص أو ملف/صوت) بـIndexedDB، ونعيد إرسالها
 * تلقائياً (fetch) أول ما يرجع الاتصال.
 *
 * **إصلاح أمان بيانات (بند 53)**: كل راوت بهذا المشروع يتبع نمط موحَّد —
 * فشل تحقّق (نفاد مخزون، حظر نحاس، بوابة دورة إنتاج...) = flash خطأ +
 * إعادة توجيه لنفس صفحة النموذج؛ نجاح = إعادة توجيه لصفحة مختلفة
 * (قائمة/تفاصيل). الإصدار القديم كان يعتبر أي رد HTTP ناجح (res.ok)
 * "نجاح" ويحذف من الطابور بصمت — لو رجع فعلياً لنفس صفحة النموذج (يعني
 * السيرفر رفض العملية تحقّقياً)، هذا كان يُفقد بيانات صامتاً. الآن نقارن
 * `res.url` (الرابط النهائي بعد أي إعادة توجيه) بالرابط الأصلي: تطابق =
 * فشل تحقّق يبقى ظاهراً بلوحة مراجعة صريحة، اختلاف = نجاح حقيقي يُحذف.
 */
(function () {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(function () {});
  }

  var DB_NAME = "murabi_offline";
  var STORE = "pending_submissions";

  function openDb() {
    return new Promise(function (resolve, reject) {
      var req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = function () {
        req.result.createObjectStore(STORE, { keyPath: "id", autoIncrement: true });
      };
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error); };
    });
  }

  function withStore(mode, fn) {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(STORE, mode);
        var result = fn(tx.objectStore(STORE));
        tx.oncomplete = function () { resolve(result); };
        tx.onerror = function () { reject(tx.error); };
      });
    });
  }

  function queueSubmission(record) {
    record.status = "pending"; // pending | failed (رُفضت تحقّقياً عند إعادة الإرسال)
    return withStore("readwrite", function (store) { store.add(record); });
  }

  function getAll() {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(STORE, "readonly");
        var req = tx.objectStore(STORE).getAll();
        req.onsuccess = function () { resolve(req.result); };
        req.onerror = function () { reject(req.error); };
      });
    });
  }

  function removeRow(id) {
    return withStore("readwrite", function (store) { store.delete(id); });
  }

  function markFailed(id, reasonNote) {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(STORE, "readwrite");
        var store = tx.objectStore(STORE);
        var getReq = store.get(id);
        getReq.onsuccess = function () {
          var row = getReq.result;
          if (row) {
            row.status = "failed";
            row.failed_note = reasonNote || "";
            store.put(row);
          }
        };
        tx.oncomplete = function () { resolve(); };
        tx.onerror = function () { reject(tx.error); };
      });
    });
  }

  function markPending(id) {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(STORE, "readwrite");
        var store = tx.objectStore(STORE);
        var getReq = store.get(id);
        getReq.onsuccess = function () {
          var row = getReq.result;
          if (row) { row.status = "pending"; delete row.failed_note; store.put(row); }
        };
        tx.oncomplete = function () { resolve(); };
        tx.onerror = function () { reject(tx.error); };
      });
    });
  }

  function formToRecord(form) {
    var fd = new FormData(form);
    var entries = [];
    fd.forEach(function (value, key) {
      entries.push({ key: key, value: value }); // value ممكن نص أو File/Blob — IndexedDB يخزّن الاثنين مباشرة
    });
    return {
      url: form.action,
      title: document.title,
      created_at: new Date().toISOString(),
      entries: entries,
    };
  }

  function recordToFormData(record) {
    var fd = new FormData();
    record.entries.forEach(function (e) { fd.append(e.key, e.value); });
    return fd;
  }

  function samePath(urlA, urlB) {
    try {
      return new URL(urlA, location.origin).pathname === new URL(urlB, location.origin).pathname;
    } catch (e) {
      return false;
    }
  }

  function updateBadges() {
    getAll().then(function (rows) {
      var pending = rows.filter(function (r) { return r.status !== "failed"; });
      var failed = rows.filter(function (r) { return r.status === "failed"; });

      document.querySelectorAll("[data-offline-badge]").forEach(function (el) { el.textContent = pending.length; });
      document.querySelectorAll("[data-offline-pending-wrap]").forEach(function (el) {
        el.style.display = pending.length ? "" : "none";
      });

      document.querySelectorAll("[data-offline-failed-badge]").forEach(function (el) { el.textContent = failed.length; });
      document.querySelectorAll("[data-offline-failed-wrap]").forEach(function (el) {
        el.style.display = failed.length ? "" : "none";
      });
      renderFailedList(failed);
    }).catch(function () {});
  }

  function renderFailedList(failedRows) {
    var container = document.querySelector("[data-offline-failed-list]");
    if (!container) return;
    container.innerHTML = "";
    failedRows.forEach(function (row) {
      var item = document.createElement("div");
      item.className = "flash warning";
      item.style.position = "static";
      item.style.marginBottom = "8px";

      var text = document.createElement("div");
      text.textContent = "⚠️ " + row.title + " — " + (window.OFFLINE_REJECTED_LABEL || "رُفضت من السيرفر عند المزامنة، راجعها وأعد الإدخال يدوياً أو أعد المحاولة.");
      item.appendChild(text);

      var actions = document.createElement("div");
      actions.style.marginTop = "6px";
      actions.style.display = "flex";
      actions.style.gap = "8px";

      var retryBtn = document.createElement("button");
      retryBtn.type = "button";
      retryBtn.className = "btn light";
      retryBtn.style.padding = "4px 10px";
      retryBtn.style.fontSize = "12px";
      retryBtn.textContent = window.OFFLINE_RETRY_LABEL || "إعادة المحاولة";
      retryBtn.addEventListener("click", function () {
        markPending(row.id).then(function () { updateBadges(); flushQueue(); });
      });

      var discardBtn = document.createElement("button");
      discardBtn.type = "button";
      discardBtn.className = "btn light";
      discardBtn.style.padding = "4px 10px";
      discardBtn.style.fontSize = "12px";
      discardBtn.textContent = window.OFFLINE_DISCARD_LABEL || "تجاهل نهائياً";
      discardBtn.addEventListener("click", function () {
        if (!confirm(window.OFFLINE_DISCARD_CONFIRM || "تجاهل هذا الإدخال نهائياً بدون رفعه؟")) return;
        removeRow(row.id).then(updateBadges);
      });

      actions.appendChild(retryBtn);
      actions.appendChild(discardBtn);
      item.appendChild(actions);
      container.appendChild(item);
    });
  }

  function flushQueue() {
    if (!navigator.onLine) return;
    getAll().then(function (rows) {
      rows.filter(function (r) { return r.status !== "failed"; }).forEach(function (row) {
        fetch(row.url, { method: "POST", body: recordToFormData(row), credentials: "same-origin" })
          .then(function (res) {
            if (res.status >= 500) {
              // خطأ سيرفر حقيقي — يبقى بلوحة المراجعة، مو إعادة محاولة لا نهائية صامتة
              markFailed(row.id, "server_error_" + res.status).then(updateBadges);
              return;
            }
            if (samePath(res.url, row.url)) {
              // نفس صفحة النموذج = نمط الفشل التحقّقي الموحَّد بكل راوتات المشروع
              markFailed(row.id, "validation_rejected").then(updateBadges);
              return;
            }
            // رابط مختلف (قائمة/تفاصيل) = نجاح حقيقي
            removeRow(row.id).then(updateBadges);
          })
          .catch(function () {
            // فشل شبكة فعلي (مو تحقّقي) — يبقى بالطابور، تُعاد المحاولة تلقائياً لاحقاً
          });
      });
    });
  }

  function setBannerVisible(offline) {
    document.querySelectorAll("[data-offline-banner]").forEach(function (el) {
      el.style.display = offline ? "" : "none";
    });
  }

  function attachFormInterception() {
    document.querySelectorAll("form[data-offline]").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        if (event.defaultPrevented) return; // اتصال أُلغي مسبقاً (مثلاً confirm() برجع false) — ما نتدخّل
        if (navigator.onLine) return; // اتصال متوفر — إرسال طبيعي بدون أي تدخّل
        event.preventDefault();
        queueSubmission(formToRecord(form)).then(function () {
          updateBadges();
          var msg = document.createElement("div");
          msg.className = "flash success";
          // النص مترجَم عبر window.OFFLINE_QUEUED_MESSAGE (بند اللغات، 2026-07-23)
          // — يُعرَّف بـ_offline_widgets.html حسب لغة المستخدم؛ عربي احتياطي لو غير معرّف.
          msg.textContent = window.OFFLINE_QUEUED_MESSAGE || "ما فيه إنترنت الآن — تم حفظ البيانات محلياً وراح تُرفع تلقائياً أول ما يرجع الاتصال.";
          form.parentNode.insertBefore(msg, form);
          form.reset();
        });
      });
    });
  }

  window.addEventListener("online", function () { setBannerVisible(false); flushQueue(); });
  window.addEventListener("offline", function () { setBannerVisible(true); });

  document.addEventListener("DOMContentLoaded", function () {
    setBannerVisible(!navigator.onLine);
    attachFormInterception();
    updateBadges();
    flushQueue();
  });

  // احتياط دوري — بعض المتصفحات (خصوصاً iOS Safari) ما تدعم Background
  // Sync API إطلاقاً، فهذا التايمر هو الضمانة الأساسية لإعادة المحاولة
  // حتى لو الصفحة مفتوحة بس بدون حدث "online" صريح.
  setInterval(flushQueue, 30000);
})();
