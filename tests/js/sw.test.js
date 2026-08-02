// بند إضافي 83 — أول اختبارات آلية جافاسكربت بالمشروع (نقطة 9 من قائمة
// نقاط الضعف). يشغّلها Node.js المدمج (node:test)، بدون أي حزمة npm
// إضافية: `node --test tests/js/`
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { isCacheablePath, EXCLUDED_PATH_PREFIXES, keysToEvict, MAX_CACHE_ENTRIES } = require("../../app/static/sw.js");

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
