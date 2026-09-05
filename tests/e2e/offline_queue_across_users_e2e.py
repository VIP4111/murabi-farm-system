"""SEC-01 × DATA-01 — سلوك طابور الإدخالات غير المرسَلة عند تبديل الحساب
على الجهاز المشترك (فجوة القبول رقم 4).

يجيب عن سؤالين منفصلين تماماً:

  (1) **هل مسح الكاش يحذف الطابور؟** يجب أن يكون الجواب "لا" — الطابور
      بـIndexedDB (`murabi_offline`) والمسح على Cache Storage: مخزنان
      مستقلان بالمتصفح. حذف عمل العامل غير المرسَل عند تسجيل الخروج كان
      سيكون فقدان بيانات، وهو ما يمنعه هذا الفحص. **هذا جزء من قبول SEC-01.**

  (2) **هل تبديل الحساب يرسل إدخالات المالك باسم العامل؟** `flushQueue`
      يرسل كل صف بـ`credentials: "same-origin"` أي بجلسة من يكون مسجّلاً
      وقت الإرسال، والصفوف لا تحمل هوية مُنشئها. **النتيجة المقيسة
      (2026-09-05) بهذا السيناريو تحديداً: لم يقع نَسْب خاطئ** — الصف
      يحمل رمز CSRF لجلسة المالك، فيُرفض بـ400 تحت جلسة العامل.
      ⚠️ **رفض CSRF ليس آلية عزل بين الحسابات ولا يجوز الاعتماد عليه
      كذلك**: هو أثر جانبي لتحقّق من التزوير، صالح فقط ما دام الرمز
      لم يُجدَّد. أي مسار يجدّد الرمز قبل إعادة الإرسال (أو نموذج بلا
      CSRF) يُسقِط هذه الحماية بالكامل ويقع النَسْب الخاطئ. لذلك يجب
      أن تعالج دفعة DATA-01 **ملكية الصف قبل تجديد الرمز وإعادة
      الإرسال**: وسم كل صف بمعرّف مُنشئه عند الحفظ، ورفض إرساله إن
      اختلف المستخدم الحالي — لا الاتكال على فشل الرمز.
      **الأثر الباقي (حاجب DATA-01 قائم)**: الإدخال ينتهي إلى لوحة
      "المرفوضات" عند **العامل** — عمل المالك غير المرسَل صار بيد مستخدم
      آخر يستطيع "تجاهله نهائياً". وعلى النماذج التي يختلف `action` فيها
      عن مسار صفحتها (≥20 نموذجاً: العمليات الجماعية، الرواتب، المستودعات)
      يأخذ نفس الرفض مسار `removeRow` = **حذف صامت**. يُبلَّغ هنا ولا
      يُفشل بوابة SEC-01.

التشغيل: `PYTHON=... bash tests/e2e/run_sw_e2e.sh --queue`
"""
import glob
import sys

from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8099").rstrip("/")
OWNER = ("0500000000", "change-me-123")
WORKER = ("0500000002", "worker1234")
MARK = "بلاغ-اختبار-طابور-المالك"

_c = (glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome")
      + glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/headless_shell"))
CHROME = _c[0] if _c else None

READ_QUEUE = """async () => new Promise((resolve) => {
  const req = indexedDB.open("murabi_offline", 1);
  req.onerror = () => resolve(null);
  req.onsuccess = () => {
    const db = req.result;
    if (!db.objectStoreNames.contains("pending_submissions")) return resolve([]);
    const tx = db.transaction("pending_submissions", "readonly");
    const all = tx.objectStore("pending_submissions").getAll();
    all.onsuccess = () => resolve(all.result.map(r => ({
      url: r.url, status: r.status,
      desc: (r.entries.find(e => e.key === "description") || {}).value || "",
    })));
    all.onerror = () => resolve(null);
  };
})"""

sec01_failures = []
data01_findings = []


def check(ok, label, detail=""):
    print(f"   {'✅' if ok else '❌'} {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        sec01_failures.append(label)


def login(page, phone, password):
    page.goto(BASE + "/login", wait_until="networkidle")
    page.fill('input[name="phone"]', phone)
    page.fill('input[name="password"]', password)
    page.press('input[name="password"]', "Enter")
    page.wait_for_load_state("networkidle")


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROME) if CHROME else pw.chromium.launch()
        ctx = browser.new_context()
        page = ctx.new_page()

        print("1) المالك يسجّل بلاغاً وهو بلا اتصال → يدخل الطابور المحلي")
        login(page, *OWNER)
        page.goto(BASE + "/team/reports/new", wait_until="networkidle")
        page.wait_for_timeout(500)
        ctx.set_offline(True)
        # النموذج يشترط حيواناً أو حظيرة (تحقّق بالصفحة نفسها يمنع الإرسال
        # بدونهما، و`offline_sync` يحترم ذلك ولا يضع بالطابور إدخالاً مرفوضاً
        # محلياً) — نختار أول حظيرة متاحة كما يفعل المستخدم فعلياً.
        barn_values = page.eval_on_selector_all(
            'select[name="barn_id"] option', "els => els.map(e => e.value).filter(Boolean)")
        assert barn_values, "لا حظائر بقاعدة الاختبار — شغّل flask seed"
        page.select_option('select[name="barn_id"]', barn_values[0])
        page.fill('textarea[name="description"]', MARK)
        page.evaluate("""() => {
            const f = document.querySelector('form[data-offline]');
            if (f) f.requestSubmit ? f.requestSubmit() : f.submit();
        }""")
        page.wait_for_timeout(900)
        q1 = page.evaluate(READ_QUEUE)
        queued = [r for r in (q1 or []) if MARK in (r.get("desc") or "")]
        print(f"   الطابور: {q1}")
        check(bool(queued), "الإدخال دخل الطابور المحلي فعلاً (شرط صحة الاختبار)")

        print("\n2) انتقال الجهاز لمستخدم آخر — هل ينجو الطابور؟")
        # ملاحظة منهجية: لا نستخدم /logout هنا. بعودة الاتصال قبل الخروج
        # يفرّغ `flushQueue` الطابور فوراً تحت جلسة المالك نفسه (السلوك
        # الصحيح، وقِسناه فعلاً). الحالة العابرة الحقيقية هي أن يبقى
        # الطابور ممتلئاً حتى بعد زوال جلسة المالك — نحاكيها بمسح كوكي
        # الجلسة والجهاز ما زال بلا اتصال (انتهاء جلسة/انتقال الجهاز).
        page.evaluate("() => caches.keys().then(ks => Promise.all(ks.map(k => caches.delete(k))))")
        page.wait_for_timeout(400)
        ctx.clear_cookies()
        ctx.set_offline(False)
        page.wait_for_timeout(400)
        caches_after = page.evaluate(
            "caches.keys().then(ks => Promise.all(ks.map(k => caches.open(k).then(c => c.keys()))))"
            ".then(a => a.flat().map(r => new URL(r.url).pathname).filter(p => !p.startsWith('/static/')))")
        q2 = page.evaluate(READ_QUEUE)
        survived = [r for r in (q2 or []) if MARK in (r.get("desc") or "")]
        print(f"   صفحات بالكاش بعد المسح: {caches_after}")
        print(f"   الطابور بعد المسح: {q2}")
        check(not caches_after, "الكاش مُسِح بالكامل")
        check(bool(survived), "طابور الإدخالات غير المرسَلة **نجا** من مسح الكاش")

        print("\n3) العامل يدخل على نفس الجهاز — ماذا يحدث بإدخال المالك؟")
        posts = []
        page.on("response", lambda r: posts.append((r.request.method, r.url.replace(BASE, ""), r.status))
                if r.request.method == "POST" else None)
        login(page, *WORKER)
        page.wait_for_timeout(3500)   # flushQueue: عند DOMContentLoaded وعند online وكل 30 ثانية
        q3 = page.evaluate(READ_QUEUE)
        mine = [r for r in (q3 or []) if MARK in (r.get("desc") or "")]
        replayed = [p for p in posts if p[1].startswith("/team/reports/new")]
        page.goto(BASE + "/team/reports", wait_until="networkidle")
        misattributed = MARK in page.content()
        print(f"   الطابور بعد دخول العامل: {q3}")
        print(f"   إعادة الإرسال تحت جلسة العامل: {replayed}")
        print(f"   نُسِب البلاغ للعامل؟ {misattributed}")

        # لا نَسْب خاطئ **بهذا السيناريو** — رمز CSRF لجلسة المالك يُرفض
        # تحت جلسة العامل. ليست حماية عزل: تسقط بمجرد تجديد الرمز.
        check(not misattributed,
              "إدخال المالك لم يُنسَب للعامل بهذا السيناريو (رفض CSRF — ليس آلية عزل)")

        if replayed and any(st >= 400 for _, _, st in replayed):
            data01_findings.append(
                f"أُعيد إرسال إدخال المالك تحت جلسة العامل ورُفض ({replayed}) — "
                "لا نَسْب خاطئ، لكنه انتهى بحالة failed داخل لوحة مراجعة **العامل**، "
                "الذي يستطيع 'تجاهله نهائياً' فيضيع عمل المالك غير المرسَل.")
        if mine and mine[0].get("status") == "failed":
            data01_findings.append(
                "الصف صار status=failed بلوحة مستخدم آخر — وعلى النماذج التي يختلف "
                "`action` فيها عن مسار صفحتها يأخذ نفس الرفض مسار removeRow (حذف صامت).")
        browser.close()

    print("\n=== نتيجة قبول SEC-01 (الطابور لا يُحذف بالمسح) ===")
    if sec01_failures:
        print(f"❌ فشل {len(sec01_failures)}: {sec01_failures}")
    else:
        print("✅ مسح الكاش لا يمسّ طابور الإدخالات — صفر فقدان بيانات")

    print("\n=== حاجب DATA-01 قائم (خارج نطاق SEC-01) ===")
    if data01_findings:
        for f in data01_findings:
            print(f"  ⚠️  {f}")
        print("  ⇒ الجذر: `offline_sync.flushQueue` يرسل كل صف بجلسة من يكون")
        print("     مسجّلاً وقت الإرسال، والصفوف لا تحمل هوية مُنشئها.")
        print("     الإصلاح يخص دفعة DATA-01: وسم كل صف بمعرّف المستخدم عند")
        print("     الحفظ، وإرساله فقط لو طابق المستخدم الحالي.")
        print("  ⚠️  عدم وقوع النَسْب الخاطئ أعلاه سببه رفض CSRF بهذا السيناريو فقط،")
        print("     ولا يصحّ اعتباره آلية عزل بين الحسابات: يسقط فور تجديد الرمز.")
        print("     لذا على دفعة DATA-01 معالجة ملكية الصف **قبل** أي تجديد للرمز")
        print("     وإعادة إرسال.")
    else:
        print("  لم يُرصد إرسال عابر للمستخدمين بهذي التشغيلة (قد يحتاج مهلة أطول).")

    return 1 if sec01_failures else 0


if __name__ == "__main__":
    sys.exit(main())
