// إصلاح — بلاغ مستخدم حقيقي: بعد تدوير مفاتيح VAPID (خلل صيغة سابق)،
// اشتراك جهاز بالمفتاح العام القديم يفشل بصمت بخطأ "VapidPkHashMismatch"
// من خادم الدفع. arrayBufferToBase64Url هي الدالة الصرفة المستخدمة
// لمقارنة مفتاح الاشتراك المحلي بالمفتاح الحالي من الخادم واكتشاف
// هذا التدوير قبل أي محاولة إرسال.
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const {
  urlBase64ToUint8Array, pushNotificationsSupported, arrayBufferToBase64Url,
} = require("../../app/static/push_notifications.js");

test("urlBase64ToUint8Array: decodes a real VAPID-style public key without throwing", () => {
  const sample = "BHKV0EAWFnzAdKz1-XlHwMZNUaUC7DoVknUCWomf5MhTqQH3Eo6C4iR1BDNgfvZIsBDGxt-As_wWpVGRICroYBY";
  const bytes = urlBase64ToUint8Array(sample);
  assert.ok(bytes instanceof Uint8Array);
  assert.equal(bytes.length, 65); // نقطة EC غير مضغوطة: 0x04 + 32 + 32 بايت
  assert.equal(bytes[0], 0x04);
});

test("arrayBufferToBase64Url: round-trips with urlBase64ToUint8Array (same key in and out)", () => {
  const original = "BHKV0EAWFnzAdKz1-XlHwMZNUaUC7DoVknUCWomf5MhTqQH3Eo6C4iR1BDNgfvZIsBDGxt-As_wWpVGRICroYBY";
  const bytes = urlBase64ToUint8Array(original);
  const roundTripped = arrayBufferToBase64Url(bytes.buffer);
  assert.equal(roundTripped, original);
});

test("arrayBufferToBase64Url: different keys produce different output (detects VAPID key rotation)", () => {
  const keyA = urlBase64ToUint8Array("BHKV0EAWFnzAdKz1-XlHwMZNUaUC7DoVknUCWomf5MhTqQH3Eo6C4iR1BDNgfvZIsBDGxt-As_wWpVGRICroYBY");
  const keyB = urlBase64ToUint8Array("BNm580GTXm4ZE9IbxnQau2LE2UoBntfcsVoHLg3-0wnII2IxthXzOEQpSsF-dbq9dZwQIjT2zGGhVg0V9MtFJag");
  assert.notEqual(arrayBufferToBase64Url(keyA.buffer), arrayBufferToBase64Url(keyB.buffer));
});

test("pushNotificationsSupported: exists as a function (DOM-dependent, only shape checked here)", () => {
  assert.equal(typeof pushNotificationsSupported, "function");
});
