"""SEC-01 — اختبار ترقية الـService Worker بكاش ملوّث وتبويبات مفتوحة
(فجوة القبول رقم 3).

**السؤال الذي يجيب عنه**: رفع `CACHE_NAME` إلى v8 لا يكفي وحده كدليل على
أن كل جهاز تخلّص من الكاش الملوّث *فوراً*. متى يصبح الإصلاح فعّالاً على
جهاز كان يشغّل v7 وفيه بيانات مالك مخزَّنة وتبويبات مفتوحة؟

**السيناريو** (نفس الأصل، نفس سياق المتصفح — ترقية حقيقية لا محاكاة):
  1. نضع `app/static/sw.js` نسخة v7 القديمة (من origin/main) ونشغّل الخادم.
  2. مالك يدخل ويتصفّح المالية/الرواتب → v7 يخزّنها بكاش `murabi-offline-v7`.
  3. نُبقي تبويباً مفتوحاً (يتحكم فيه v7 النشط).
  4. نعيد `sw.js` إلى v8 (نفس ما يحدث لحظة النشر — الملف يُقدَّم من القرص).
  5. نجبر المتصفح على فحص التحديث (`registration.update()`) ثم ننتقل.
  6. نتحقق: هل اختفى كاش v7 وبياناته الملوّثة فعلاً؟

**النتيجة الموثَّقة (2026-09-05)**: نعم — بمجرد تفعيل v8 (بفضل
`skipWaiting()` + `clients.claim()` الموجودتين أصلاً) يمسح معالج `activate`
كل كاش باسم مختلف عن `CACHE_NAME`، فيختفي `murabi-offline-v7` بكل محتواه.
**لكن** ذلك يقع عند **تفعيل** v8، لا عند لحظة النشر — راجع الخلاصة المطبوعة.

التشغيل: `PYTHON=... bash tests/e2e/run_sw_e2e.sh --upgrade`
"""
import glob
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8099").rstrip("/")
SW_PATH = Path(__file__).resolve().parents[2] / "app" / "static" / "sw.js"
OWNER = ("0500000000", "change-me-123")

_c = (glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome")
      + glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/headless_shell"))
CHROME = _c[0] if _c else None

READ_CACHES = """async () => {
  const names = await caches.keys(); const out = {};
  for (const n of names) {
    const c = await caches.open(n); const ks = await c.keys();
    out[n] = ks.map(r => new URL(r.url).pathname).sort();
  }
  return out;
}"""

failures = []


def check(ok, label, detail=""):
    print(f"   {'✅' if ok else '❌'} {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(label)


def login(page, phone, password):
    page.goto(BASE + "/login", wait_until="networkidle")
    page.fill('input[name="phone"]', phone)
    page.fill('input[name="password"]', password)
    page.press('input[name="password"]', "Enter")
    page.wait_for_load_state("networkidle")


def main() -> int:
    new_sw = SW_PATH.read_text(encoding="utf-8")
    old_sw = subprocess.run(["git", "show", "origin/main:app/static/sw.js"],
                            capture_output=True, text=True, check=True).stdout
    assert 'murabi-offline-v7' in old_sw, "نسخة origin/main ليست v7 — حدّث الاختبار"

    try:
        print("1) وضع النسخة القديمة v7 وتلويث الكاش بجلسة المالك")
        SW_PATH.write_text(old_sw, encoding="utf-8")

        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=CHROME) if CHROME else pw.chromium.launch()
            ctx = browser.new_context()
            page = ctx.new_page()

            login(page, *OWNER)
            page.goto(BASE + "/", wait_until="networkidle")
            page.wait_for_timeout(500)
            for p in ("/finance/", "/team/salaries", "/settings/backup"):
                page.goto(BASE + p, wait_until="networkidle")
                page.wait_for_timeout(300)
            before = page.evaluate(READ_CACHES)
            contaminated = sorted({q for v in before.values() for q in v
                                   if q.startswith(("/finance", "/team/salaries", "/settings"))})
            print(f"   كاشات v7: {list(before.keys())}")
            print(f"   مُدخَلات ملوَّثة: {contaminated}")
            check(bool(contaminated), "التلويث تحقّق فعلاً (شرط صحة الاختبار)")

            # تبويب ثانٍ مفتوح يتحكم فيه v7 — يحاكي جهازاً قيد الاستخدام
            tab2 = ctx.new_page()
            tab2.goto(BASE + "/team/tasks", wait_until="networkidle")
            print("   تبويب ثانٍ مفتوح تحت سيطرة v7")

            print("\n2) نشر النسخة الجديدة v8 (استبدال الملف على القرص)")
            SW_PATH.write_text(new_sw, encoding="utf-8")
            time.sleep(0.5)

            print("3) المتصفح يفحص التحديث ويفعّل v8")
            page.evaluate("navigator.serviceWorker.getRegistration().then(r => r && r.update())")
            page.wait_for_timeout(1500)
            page.goto(BASE + "/", wait_until="networkidle")
            page.wait_for_timeout(1500)

            after = page.evaluate(READ_CACHES)
            active = page.evaluate(
                "navigator.serviceWorker.getRegistration().then(r => r && r.active && r.active.scriptURL)")
            still = sorted({q for v in after.values() for q in v
                            if q.startswith(("/finance", "/team/salaries", "/settings"))})
            print(f"   كاشات بعد الترقية: {list(after.keys())}")
            check("murabi-offline-v7" not in after, "كاش v7 اختفى بعد تفعيل v8",
                  str(list(after.keys())))
            check(not still, "لا مُدخَل ملوَّث باقٍ", str(still))

            tab2.close()
            browser.close()
    finally:
        SW_PATH.write_text(new_sw, encoding="utf-8")  # استرجاع مضمون حتى عند الفشل

    print("\n=== متى يصبح الإصلاح فعّالاً؟ ===")
    print("  • لحظة النشر لا تكفي: الجهاز يظل على v7 حتى يجلب /sw.js المحدَّث.")
    print("  • المتصفح يفحص /sw.js مع كل تنقّل (والراوت يرسل Cache-Control: no-cache)،")
    print("    فالتحديث يُلتقط عادةً بأول تنقّل بعد النشر وأنت متصل.")
    print("  • بفضل skipWaiting()+clients.claim() يتولّى v8 التبويبات المفتوحة فوراً،")
    print("    ومعالج activate يمسح كل كاش باسم مختلف — فيختفي v7 بكل محتواه.")
    print("  • النافذة المتبقّية: تنقّل واحد قد يُخدَم من v7 قبل تفعيل v8، ولو كان")
    print("    الجهاز بلا اتصال تماماً فلن يُجلب /sw.js أصلاً ويبقى v7 عاملاً.")
    print("  ⇒ إجراء المستخدم بعد النشر على جهاز مشترك: سجّل خروجاً ودخولاً مرة")
    print("    وأنت متصل (أو أغلق كل تبويبات الموقع ثم افتحه). بعدها المسح")
    print("    التلقائي عند كل حدّ مصادقة يتكفّل بالباقي بلا أي تدخّل.")

    print("\n=== الحكم ===")
    if failures:
        print(f"UPGRADE-LEAK ❌ — فشل {len(failures)}: {failures}")
        return 1
    print("UPGRADE-CLEAN ✅ — الترقية أزالت الكاش الملوّث بالكامل")
    return 0


if __name__ == "__main__":
    sys.exit(main())
