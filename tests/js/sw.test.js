// بند إضافي 83 — أول اختبارات آلية جافاسكربت بالمشروع (نقطة 9 من قائمة
// نقاط الضعف). يشغّلها Node.js المدمج (node:test)، بدون أي حزمة npm
// إضافية: `node --test tests/js/`
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const {
  isCacheablePath, EXCLUDED_PATH_PREFIXES, keysToEvict, MAX_CACHE_ENTRIES,
  raceNetworkWithTimeout, NETWORK_TIMEOUT_MS,
} = require("../../app/static/sw.js");

const ORIGIN = "https://murabi-farm-system.onrender.com";

test("isCacheablePath: same-origin page not excluded → true", () => {
  assert.equal(isCacheablePath(ORIGIN + "/team/tasks", ORIGIN), true);
  assert.equal(isCacheablePath(ORIGIN + "/reports/activity", ORIGIN), true);
});

test("isCacheablePath: excluded prefixes → false (بند 82)", () => {
  for (const prefix of EXCLUDED_PATH_PREFIXES) {
    assert.equal(isCacheablePath(ORIGIN + prefix + "x", ORIGIN), false, prefix);
  }
});

test("isCacheablePath: cross-origin request → false", () => {
  assert.equal(isCacheablePath("https://evil.com/team/tasks", ORIGIN), false);
});

test("isCacheablePath: malformed URL → false, never throws", () => {
  assert.equal(isCacheablePath("not a url", ORIGIN), false);
});

// بند إضافي 91 (نقطة 7) — تقليم الكاش بدون حد أقصى سابق
test("keysToEvict: under the limit → nothing to evict", () => {
  const urls = Array.from({ length: 50 }, (_, i) => `${ORIGIN}/page/${i}`);
  assert.deepEqual(keysToEvict(urls, MAX_CACHE_ENTRIES), []);
});

test("keysToEvict: over the limit → evicts oldest first (FIFO)", () => {
  const urls = Array.from({ length: 155 }, (_, i) => `${ORIGIN}/page/${i}`);
  const evicted = keysToEvict(urls, 150);
  assert.equal(evicted.length, 5);
  assert.deepEqual(evicted, urls.slice(0, 5));
});

test("keysToEvict: exactly at the limit → nothing to evict", () => {
  const urls = Array.from({ length: 150 }, (_, i) => `${ORIGIN}/page/${i}`);
  assert.deepEqual(keysToEvict(urls, 150), []);
});

// بند إضافي 201 — قبل هذا البند، fetch() لطلب على شبكة ميتة فعلياً (لا
// خطأ سيرفر، بس صفر اتصال) ممكن يعلّق طويل جداً على iOS Safari تحديداً
// قبل ما يرفض الوعد، فمستخدم الآيفون يشوف "تحميل" بلا نهاية بدل النسخة
// المخزَّنة اللي كانت جاهزة. هذي الاختبارات تتحقق من سلوك السباق نفسه
// بمعزل عن بيئة Service Worker حقيقية (بدون محاكاة self/caches كاملة).
test("raceNetworkWithTimeout: fast network response wins over timeout", async () => {
  const fastNetwork = Promise.resolve("network-response");
  const result = await raceNetworkWithTimeout(fastNetwork, 4000, (ms) => new Promise(() => {})); // timeout never fires
  assert.equal(result, "network-response");
});

test("raceNetworkWithTimeout: network that never resolves falls back to timeout (null)", async () => {
  const hangingNetwork = new Promise(() => {}); // يحاكي fetch() المعلَّق على شبكة ميتة
  const fastTimeout = (ms) => Promise.resolve(null); // مهلة "تنتهي فوراً" وقت الاختبار
  const result = await raceNetworkWithTimeout(hangingNetwork, 4000, fastTimeout);
  assert.equal(result, null);
});

test("NETWORK_TIMEOUT_MS: a real, sane value (not accidentally 0 or absurdly long)", () => {
  assert.ok(NETWORK_TIMEOUT_MS > 0 && NETWORK_TIMEOUT_MS <= 10000);
});
