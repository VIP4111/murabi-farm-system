"""SEC-01 — اختبار قبول بمتصفح حقيقي (Chromium عبر Playwright): عزل كاش
الـService Worker بين مستخدمي **الجهاز الواحد المشترك**.

يُشغَّل بأمر واحد يجهّز كل شي وينظّفه:  `bash tests/e2e/run_sw_e2e.sh`
وهو أيضاً جزء من pytest عبر `tests/test_sec01_e2e_browser.py` (يُتخطّى
بسبب صريح حيث لا يتوفر Playwright/Chromium).

يغطي خمسة سيناريوهات، كلها على **سياق متصفح واحد** = Cache Storage واحد
= جهاز واحد يتناوب عليه مستخدمان:

  A) العزل الأساسي: مالك يتصفّح ⇒ خروج ⇒ عامل يدخل.
     يثبت: لا شاشة حسّاسة تُخزَّن أصلاً، والكاش يُمسح عند الخروج.

  B) المحتوى الفعلي تحت انقطاع الشبكة (فجوة القبول 6): بعد دخول العامل
     نقطع الشبكة تماماً ونطلب صفحات زارها المالك. يثبت أن العامل لا يُقدَّم
     له محتوى المالك فعلياً — لا مجرد أن Cache Storage فارغ. نبحث عن
     بصمات نصية من صفحات المالك بالـDOM المعروض.

  C) **حارس الحقبة برد محتجَز فعلياً** (فجوة القبول 2): نطلب مورداً
     **قابلاً للتخزين حقاً** (`/static/…`) ونحتجز ردّه بالمعترض فلا يصل
     إطلاقاً، ثم نخرج، ثم نُطلقه **بعد** اكتمال الخروج. فالترتيب مفروض لا
     مُقدَّر: يستحيل أن يصل الرد قبل الخروج لأننا نحن من يطلقه. بلا حارس
     الحقبة كان هذا الرد يُكتب بالكاش بعد تنظيفه (المسار ضمن قائمة السماح)،
     فوجوده أو غيابه بالكاش فحص يميّز فعلاً. ونفحص معه ألا تعود أي صفحة
     HTML للكاش.

  D) **ترتيب تبديل الهوية بخروج محتجَز** (فجوة القبول 4 + مراجعة الترتيب):
     تبويب بقي مفتوحاً على صفحة المالك، ونحتجز ردّ `/logout` نفسه. أثناء
     الاحتجاز — والجلسة على الخادم **ما زالت مفتوحة** — نتحقق أن التبويب:
     (1) حجب بيانات المالك فوراً، و(2) **لم** يعد تحميل الصفحة المحمية
     (لو فعل لقرأها بالجلسة القديمة وعرض بيانات المالك طازجة). ثم نطلق
     الخروج ونتحقق أنه أعاد التحميل وانتهى لصفحة الدخول. الفحص على
     **المحتوى بعد اكتمال الخروج**، لا على وصول رسالة.

  E) **فحص ما بعد النشر** (فجوة القبول 5): نشغّل `sw_post_deploy_check.js`
     — نفس الملف الذي يلصقه المستخدم بأدوات المطوّر — ونتأكد أنه يعطي PASS
     على جهاز مُحدَّث فعلاً. أي أن أداة التحقق نفسها مُختبَرة، لا مجرد نصيحة.

يخرج بـ0 عند ISOLATED ✅ و1 عند LEAK ❌.
"""
import glob
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8099").rstrip("/")
OWNER = ("0500000000", "change-me-123")
WORKER = ("0500000002", "worker1234")
SENSITIVE_PREFIXES = ("/finance", "/settings", "/team/salaries", "/team/payroll",
                      "/team/members", "/reports", "/assistant")

# بصمات نصية تظهر حصراً بصفحات المالك الحسّاسة (فجوة القبول 6) — وجود أيٍّ
# منها بصفحة يراها العامل = تسريب محتوى فعلي، لا مجرد أثر بالكاش.
OWNER_ONLY_MARKERS = ["صافي الربح", "الراتب الأساسي", "نسخة احتياطية كاملة"]

POST_DEPLOY_CHECK = (Path(__file__).parent / "sw_post_deploy_check.js").read_text(encoding="utf-8")

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


class HeldRequest:
    """يحتجز ردّ طلب بعينه حتى نطلقه صراحةً — فالترتيب مفروض لا مُقدَّر.

    معالج المسار بـPlaywright لا يجب أن يحجب الخيط، فنحتفظ بكائن الطلب
    ونُكمله لاحقاً من الخيط الرئيسي. بين اللحظتين يبقى الرد معلَّقاً فعلياً
    على الشبكة — وهو ما يجعل «وصل بعد الخروج» حقيقة لا افتراضاً زمنياً.
    """

    def __init__(self, ctx, predicate):
        self.route = None
        ctx.route(predicate, self._hold)

    def _hold(self, route):
        if self.route is None:
            self.route = route          # لا continue_ الآن — الرد محتجَز
        else:
            route.continue_()

    def wait_until_held(self, pump_page, timeout_ms=15000):
        waited = 0
        while self.route is None and waited < timeout_ms:
            pump_page.wait_for_timeout(100)   # يدوّر حلقة أحداث Playwright
            waited += 100
        return self.route is not None

    def release(self):
        assert self.route is not None, "لم يصل الطلب المحتجَز أصلاً"
        self.route.continue_()


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

        # ---------- C) رد محتجَز فعلياً على مسار قابل للتخزين ----------
        print("\nC) حارس الحقبة برد محتجَز حتى ما بعد الخروج")
        tab2 = ctx.new_page()
        tab2.goto(BASE + "/team/tasks", wait_until="networkidle")

        # المورد المطلوب **ضمن قائمة السماح** (/static/) — أي أنه يُخزَّن
        # فعلاً لولا حارس الحقبة، فالفحص يميّز بين وجود الحارس وغيابه.
        LATE_ASSET = "/static/offline_sync.js?sec01-late=1"
        late = HeldRequest(ctx, lambda url: "sec01-late=1" in url)
        tab2.evaluate("""() => {
            window.__lateDone = false;
            fetch('%s', {credentials: 'same-origin'})
              .then(r => r.text()).then(() => { window.__lateDone = true; })
              .catch(() => { window.__lateDone = 'error'; });
        }""" % LATE_ASSET)
        check(late.wait_until_held(tab2), "الطلب المتأخر احتُجز فعلاً قبل الخروج (شرط صحة الاختبار)")
        check(tab2.evaluate("window.__lateDone") is False,
              "الرد المحتجَز لم يصل بعد — الترتيب مفروض لا مُقدَّر")

        # ---------- D) تبويب قديم + خروج محتجَز ----------
        # التبويب يبقى مفتوحاً على صفحة مالية المالك، ونحتجز ردّ /logout
        # نفسه لنفحص ما يفعله التبويب **والجلسة ما زالت مفتوحة**.
        print("\nD) ترتيب تبديل الهوية بخروج محتجَز")
        stale_tab = ctx.new_page()
        stale_tab.goto(BASE + "/finance/", wait_until="networkidle")
        stale_tab.wait_for_timeout(300)
        check("صافي الربح" in stale_tab.content(),
              "التبويب القديم كان يعرض بيانات المالك قبل الخروج (شرط صحة الاختبار)")
        # علامة تختفي مع أي إعادة تحميل — بها نثبت أن التبويب لم يُعِد
        # قراءة الصفحة المحمية قبل تأكيد اكتمال الخروج.
        stale_tab.evaluate("window.__murabiNoReloadYet = 1")

        held_logout = HeldRequest(ctx, lambda url: url.rstrip("/").endswith("/logout"))
        # ننتقل بلا انتظار: الرد محتجَز، فـgoto كانت ستُجمّد الخيط.
        page.evaluate("setTimeout(() => { window.location.href = '/logout'; }, 0)")
        check(held_logout.wait_until_held(stale_tab), "ردّ /logout احتُجز فعلاً (شرط صحة الاختبار)")

        # الجلسة على الخادم ما زالت مفتوحة الآن — هذي هي اللحظة الحرجة.
        stale_tab.wait_for_timeout(800)
        mid_body = stale_tab.content()
        mid_marker = stale_tab.evaluate("window.__murabiNoReloadYet")
        mid_found = [m for m in OWNER_ONLY_MARKERS if m in mid_body]
        check(not mid_found,
              "بيانات المالك أُزيلت من المستند فور بدء التبديل، قبل اكتمال الخروج",
              str(mid_found))
        check("صافي الربح" not in stale_tab.title(),
              "ولا عنوان التبويب يكشف شاشة الحساب السابق", stale_tab.title())
        check(mid_marker == 1,
              "التبويب لم يُعِد قراءة الصفحة المحمية قبل تأكيد اكتمال الخروج",
              f"marker={mid_marker}")

        # الآن نُطلق الخروج ونتحقق من المحتوى **بعد اكتماله**.
        held_logout.release()
        page.wait_for_url("**/login**", timeout=20000)
        check("/login" in page.url, "انتقال الخروج اكتمل ولم يُجهَض بتبليغ حدّ المصادقة", page.url)

        stale_tab.wait_for_timeout(3000)
        stale_url = stale_tab.url
        stale_body = stale_tab.content()
        check(stale_tab.evaluate("window.__murabiNoReloadYet") is None,
              "بعد اكتمال الخروج أعاد التبويب التحميل فعلاً")
        check("صافي الربح" not in stale_body,
              "التبويب القديم لا يعرض بيانات المالك بعد اكتمال الخروج")
        check("/login" in stale_url or "كلمة المرور" in stale_body,
              "التبويب القديم انتهى لصفحة الدخول", stale_url)
        stale_tab.close()

        after_logout, _ = cached_pages(page)
        check(not after_logout, "الكاش فارغ بعد تسجيل الخروج", str(after_logout))

        # ---------- إطلاق الرد المتأخر: بعد الخروج يقيناً ----------
        late.release()
        tab2.wait_for_function("window.__lateDone !== false", timeout=15000)
        tab2.wait_for_timeout(600)   # cache.put غير متزامن لو وقع
        cached_late = tab2.evaluate("""async () => {
          for (const n of await caches.keys()) {
            const c = await caches.open(n);
            const ks = await c.keys();
            const hit = ks.map(r => r.url).filter(u => u.indexOf('sec01-late=1') !== -1);
            if (hit.length) return hit;
          }
          return [];
        }""")
        check(not cached_late,
              "رد وصل بعد المسح لم يُكتب بالكاش رغم أن مساره ضمن قائمة السماح "
              "(حارس الحقبة)", str(cached_late))
        after_late, _ = cached_pages(page)
        check(not after_late, "ولا صفحة HTML عادت للكاش بعد المسح", str(after_late))
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

        # ---------- E) أداة فحص ما بعد النشر ----------
        print("\nE) أداة الفحص التي يلصقها المستخدم بأدوات المطوّر")
        page.goto(BASE + "/", wait_until="networkidle")
        page.wait_for_timeout(400)
        result = page.evaluate(POST_DEPLOY_CHECK)
        for c in result["checks"]:
            print(f"   {'✅' if c['ok'] else '❌'} {c['label']}"
                  + (f" — {c['detail']}" if c["detail"] else ""))
        check(result["pass"], "أداة فحص ما بعد النشر تعطي PASS على جهاز مُحدَّث")

        browser.close()

    print("\n=== الحكم ===")
    if failures:
        print(f"LEAK ❌ — فشل {len(failures)}: {failures}")
        return 1
    print("ISOLATED ✅ — كل الفحوص نجحت")
    return 0


if __name__ == "__main__":
    sys.exit(main())
