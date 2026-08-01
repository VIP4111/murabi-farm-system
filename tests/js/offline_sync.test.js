// بند إضافي 83 — يغطي samePath()، منطق السلامة الحرج من بند 53: يميّز
// "فشل تحقّق حقيقي" (رجوع لنفس صفحة النموذج) عن "نجاح حقيقي" (رابط
// مختلف)، عشان طابور المزامنة ما يحذف بلاغ صامتاً كان مرفوض فعلياً.
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { samePath } = require("../../app/static/offline_sync.js");

const ORIGIN = "https://murabi-farm-system.onrender.com";

test("samePath: same pathname (redirect back to form) → true", () => {
  assert.equal(samePath("/team/reports/new", "/team/reports/new", ORIGIN), true);
});

test("samePath: different pathname (redirect to list/detail) → false", () => {
  assert.equal(samePath("/team/reports/42", "/team/reports/new", ORIGIN), false);
});

test("samePath: relative vs absolute same path → true (البند 53 الأصلي كان يعتمد على هذا)", () => {
  assert.equal(samePath(ORIGIN + "/team/reports/new", "/team/reports/new", ORIGIN), true);
});

test("samePath: query string differences ignored (pathname بس يُقارَن)", () => {
  assert.equal(samePath("/team/reports/new?x=1", "/team/reports/new?y=2", ORIGIN), true);
});

test("samePath: malformed input → false, never throws", () => {
  assert.equal(samePath(null, undefined, ORIGIN), false);
});
