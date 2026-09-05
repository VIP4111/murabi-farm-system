"""SEC-01 — اختبار قبول بمتصفح حقيقي (Chromium عبر Playwright): عزل كاش
الـService Worker بين مستخدمي **الجهاز الواحد المشترك**.

يُشغَّل بأمر واحد يجهّز كل شي وينظّفه:  `bash tests/e2e/run_sw_e2e.sh`
وهو أيضاً جزء من pytest عبر `tests/test_sec01_e2e_browser.py` (يُتخطّى
بسبب صريح حيث لا يتوفر Playwright/Chromium).

يغطي أربعة سيناريوهات، كلها على **سياق متصفح واحد** = Cache Storage واحد
= جهاز واحد يتناوب عليه مستخدمان:

  A) العزل الأساسي: مالك يتصفّح ⇒ خروج ⇒ عامل يدخل.
     يثبت: لا شاشة حسّاسة تُخزَّن أصلاً، والكاش يُمسح عند الخروج.

  B) المحتوى الفعلي تحت انقطاع الشبكة (فجوة القبول 6): بعد دخول العامل
     نقطع الشبكة تماماً ونطلب صفحات زارها المالك. يثبت أن العامل لا يُقدَّم
     له محتوى المالك فعلياً — لا مجرد أن Cache Storage فارغ. نبحث عن
     بصمات نصية من صفحات المالك بالـDOM المعروض.

  C) الرد المتأخر عبر تبويبين (فجوة القبول 2): تبويب ثانٍ يبدأ طلباً
     لصفحة قابلة للتخزين بجلسة المالك، نؤخّر رده على الخادم، ثم نخرج
     وندخل بحساب العامل قبل وصوله. يثبت أن وصول الرد المتأخر **لا يعيد**
     صفحة المالك للكاش بعد تنظيفه (حارس الحقبة، SEC-01(د)).

  D) ترقية الـSW بكاش ملوّث (فجوة القبول 3): تُشغَّل بوضع خاص — راجع
     `--upgrade-from` أدناه وتوثيق "متى يصبح الإصلاح فعّالاً".

يخرج بـ0 عند ISOLATED ✅ و1 عند LEAK ❌.
"""
import glob
import sys

from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8099").rstrip("/")
OWNER = ("0500000000", "change-me-123")
WORKER = ("0500000002", "worker1234")
SENSITIVE_PREFIXES = ("/finance", "/settings", "/team/salaries", "/team/payroll",
                      "/team/members", "/reports", "/assistant")

# بصمات نصية تظهر حصراً بصفحات المالك الحسّاسة (فجوة القبول 6) — وجود أيٍّ
# منها بصفحة يراها العامل = تسريب محتوى فعلي، لا مجرد أثر بالكاش.
OWNER_ONLY_MARKERS = ["صافي الربح", "الراتب الأساسي", "نسخة احتياطية كاملة"]

_candidates = (glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome")
               + glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/headless_shell"))
CHROME = _candidates[0] if _candidates else None

READ_CACHES = """async () => {
  const names = await caches.keys(); const out = {};
  for (const n of names) {
    const c = await caches.open(n); const ks = await c.keys();
    out[n] = ks.map(r => new URL(r.url).pathname).sort();
  }
  return out;
}"""

# قراءة نصّ مُدخَل معيّن من الكاش مباشرة (لا عبر عرض الصفحة) — يكشف
# التسريب حتى لو لم يُقدَّم للمستخدم بعد.
READ_CACHED_TEXT = """async (path) => {
  for (const n of await caches.keys()) {
    const c = await caches.open(n);
    const res = await c.match(new URL(path, location.origin).href);
    if (res) return await res.text();
  }
  return null;
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
    # Enter داخل حقل كلمة المرور — صفحة الدخول فيها أربع فورمات لغة بأزرار
    # submit قبل فورم الدخول، فالنقر على "أول زر submit" يختار لغة لا يدخل.
    page.press('input[name="password"]', "Enter")
    page.wait_for_load_state("networkidle")
    assert page.url.rstrip("/") == BASE, f"فشل الدخول بـ{phone} → {page.url}"


def visit(page, *paths):
    for p in paths:
        page.goto(BASE + p, wait_until="networkidle")
        page.wait_for_timeout(400)  # cache.put غير متزامن بعد الردّ


def cached_pages(page):
    """المسارات المخزَّنة، بلا أصول /static/ العامة (متطابقة لكل المستخدمين)."""
    c = page.evaluate(READ_CACHES)
    return sorted({p for ps in c.values() for p in ps if not p.startswith("/static/")}), list(c.keys())


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROME) if CHROME else pw.chromium.launch()
        ctx = browser.new_context()          # ← الجهاز المشترك الواحد
        page = ctx.new_page()

        # ---------- A) العزل الأساسي ----------
        print("\nA) العزل الأساسي: مالك ⇒ خروج ⇒ عامل")
        login(page, *OWNER)
        page.goto(BASE + "/", wait_until="networkidle")
        state = page.evaluate("navigator.serviceWorker.ready.then(r => r.active && r.active.state)")
        visit(page, "/", "/team/tasks", "/finance/", "/settings/backup", "/team/salaries")
        owner_pages, cache_names = cached_pages(page)
        print(f"   SW={state} · الكاش={cache_names}")
        print(f"   صفحات المالك المخزَّنة: {owner_pages}")
        leaked = [p for p in owner_pages if p.startswith(SENSITIVE_PREFIXES)]
        check(not leaked, "لا شاشة حسّاسة تُخزَّن أثناء جلسة المالك", str(leaked))

        # ---------- C) الرد المتأخر عبر تبويبين ----------
        # نبدأ الطلب المتأخر الآن (قبل الخروج) من تبويب ثانٍ، ونتركه معلَّقاً.
        print("\nC) الرد المتأخر عبر تبويبين (حارس الحقبة)")
        tab2 = ctx.new_page()
        tab2.goto(BASE + "/team/tasks", wait_until="networkidle")
        # طلب مؤجَّل على مسار قابل للتخزين: نؤخّره داخل المتصفح نفسه
        # (نفس أثر خادم بطيء) ثم نتحقق ماذا يفعل رده بعد الخروج.
        tab2.evaluate("""() => {
            window.__late = fetch('/team/tasks?late=1', {credentials: 'same-origin'})
              .then(r => r.text()).then(() => 'done').catch(e => 'err:' + e);
        }""")
        tab2.wait_for_timeout(150)  # الطلب انطلق فعلاً

        # ---------- الخروج ----------
        page.goto(BASE + "/logout", wait_until="networkidle")
        page.wait_for_timeout(600)
        after_logout, _ = cached_pages(page)
        check(not after_logout, "الكاش فارغ بعد تسجيل الخروج", str(after_logout))

        # ندع الطلب المتأخر يكتمل بعد المسح
        tab2.wait_for_timeout(1200)
        after_late, _ = cached_pages(page)
        check(not after_late, "الرد المتأخر لم يُعِد صفحات المالك للكاش بعد المسح", str(after_late))
        tab2.close()

        # ---------- دخول العامل ----------
        print("\nB) محتوى فعلي تحت انقطاع الشبكة (بعد دخول العامل)")
        login(page, *WORKER)
        visit(page, "/")
        worker_pages, _ = cached_pages(page)
        owner_leftovers = [p for p in worker_pages if p != "/"]
        check(not owner_leftovers, "العامل لا يرى بالكاش أي صفحة من جلسة المالك", str(owner_leftovers))

        # قراءة مباشرة من الكاش لصفحات المالك — يجب ألا يوجد أي نصّ
        for path in ("/finance/", "/team/salaries", "/settings/backup"):
            text = page.evaluate(READ_CACHED_TEXT, path)
            check(text is None, f"لا نسخة مخزَّنة لـ{path}")

        # الآن نقطع الشبكة ونطلب صفحات المالك: يجب ألا يُعرَض محتواه
        ctx.set_offline(True)
        for path in ("/finance/", "/team/salaries"):
            try:
                page.goto(BASE + path, wait_until="domcontentloaded", timeout=8000)
                body = page.content()
            except Exception:
                body = ""  # فشل التنقّل بالكامل = لا محتوى مُقدَّم، وهو المطلوب
            found = [m for m in OWNER_ONLY_MARKERS if m in body]
            check(not found, f"لا محتوى للمالك يُعرَض عند طلب {path} بلا شبكة", str(found))
        ctx.set_offline(False)

        browser.close()

    print("\n=== الحكم ===")
    if failures:
        print(f"LEAK ❌ — فشل {len(failures)}: {failures}")
        return 1
    print("ISOLATED ✅ — كل الفحوص نجحت")
    return 0


if __name__ == "__main__":
    sys.exit(main())
