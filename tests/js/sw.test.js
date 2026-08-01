// بند إضافي 83 — أول اختبارات آلية جافاسكربت بالمشروع (نقطة 9 من قائمة
// نقاط الضعف). يشغّلها Node.js المدمج (node:test)، بدون أي حزمة npm
// إضافية: `node --test tests/js/`
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { isCacheablePath, EXCLUDED_PATH_PREFIXES } = require("../../app/static/sw.js");

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
