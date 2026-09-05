"""SEC-01 — دليل قابل لإعادة التشغيل: هل الصفحات الخمس التي كانت بقائمة
السماح "عامة" فعلاً بين المستخدمين؟

خلفية القرار: النسخة الأولى من إصلاح SEC-01 أبقت خمسة مسارات "ميدانية"
قابلة للتخزين لأن **كل الأدوار تملك صلاحية فتحها**. اشتراك المستخدمين في
صلاحية فتح صفحة لا يثبت أن مشاركتها بكاش واحد آمنة: الكاش على مستوى
الأصل (origin) لا المستخدم، فأي اختلاف بمحتوى الردّ بين حسابين يعني أن
النسخة المخزَّنة لأحدهما قابلة للتقديم للآخر.

هذا السكربت يقيس الفرق فعلياً: يسجّل الدخول بحساب المالك ثم بحساب العامل
على خادم حيّ (CSRF مفعّل، جلسات حقيقية)، يجلب المسارات الخمسة بكل حساب،
ويقارن:
  • حالة HTTP والرابط النهائي لكل دور،
  • تطابق الجسم بايتاً ببايت،
  • ظهور اسم المستخدم المسجَّل داخل الصفحة،
  • قيمة <meta name="csrf-token"> لكل دور وهل تختلف،
  • عدد حقول csrf_token المخفية داخل النماذج.

يخرج بـ0 إذا كانت **كل** المسارات تحمل بيانات جلسة/مستخدم (أي أن قرار
إخراجها من الكاش صحيح ومُثبَت)، وبـ1 لو ظهر مسار متطابق تماماً بين
الحسابين — عندها يستحق النقاش من جديد.

التشغيل: `PYTHON=... bash tests/e2e/run_sw_e2e.sh --diff`
"""
import http.cookiejar
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8099").rstrip("/")
OWNER = ("0500000000", "change-me-123", "صاحب الحلال")
WORKER = ("0500000002", "worker1234", "عامل الاختبار")

# المسارات الخمسة التي كانت بقائمة السماح (OFFLINE_FIELD_PAGE_EXACT قبل
# هذه الدفعة)، مع سبب طلب إتاحتها بلا اتصال.
PATHS = [
    ("/", "الشاشة الرئيسية — نقطة الدخول لكل شي بالميدان"),
    ("/today", "مهام اليوم — يفتحها العامل بالحظيرة حيث التغطية ضعيفة"),
    ("/alerts/mine", "تنبيهاتي — ما يخص المستخدم من تنبيهات عاجلة"),
    ("/team/tasks", "قائمة المهام — مرجع العامل أثناء الجولة"),
    ("/team/reports", "البلاغات — يُراجعها ويرفع منها بلاغاً جديداً"),
]

CSRF_META = re.compile(r'<meta name="csrf-token" content="([^"]+)"')
CSRF_INPUT = re.compile(r'name="csrf_token"[^>]*value="([^"]*)"')


def opener():
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def get(op, path):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "sec01-diff"})
    try:
        with op.open(req, timeout=20) as r:
            return r.status, r.geturl(), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, BASE + path, e.read().decode("utf-8", "replace")


def login(phone, password):
    op = opener()
    _, _, body = get(op, "/login")
    m = CSRF_INPUT.search(body)
    data = {"phone": phone, "password": password}
    if m:
        data["csrf_token"] = m.group(1)
    req = urllib.request.Request(
        BASE + "/login", data=urllib.parse.urlencode(data).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "User-Agent": "sec01-diff"})
    with op.open(req, timeout=20) as r:
        final = r.geturl()
    assert "/login" not in final, f"فشل الدخول بـ{phone} → {final}"
    return op


def main() -> int:
    print("═══ مقارنة الردّ الفعلي بين المالك والعامل للمسارات الخمسة ═══\n")
    o_op, w_op = login(*OWNER[:2]), login(*WORKER[:2])
    rows, shareable = [], []

    for path, why in PATHS:
        o_st, o_url, o_body = get(o_op, path)
        w_st, w_url, w_body = get(w_op, path)

        o_meta = (CSRF_META.search(o_body) or [None, ""])[1]
        w_meta = (CSRF_META.search(w_body) or [None, ""])[1]
        signals = []
        if o_body != w_body:
            signals.append(f"جسم مختلف ({len(o_body)}≠{len(w_body)} حرف)")
        if OWNER[2] in o_body:
            signals.append(f"يحمل اسم المستخدم «{OWNER[2]}»")
        if o_meta and w_meta and o_meta != w_meta:
            signals.append("رمز CSRF مختلف لكل جلسة")
        n_hidden = len(CSRF_INPUT.findall(o_body))
        if n_hidden:
            signals.append(f"{n_hidden} حقل csrf_token مخفي")
        if o_st != w_st or o_url != w_url:
            signals.append(f"وصول مختلف (مالك {o_st} {o_url} · عامل {w_st} {w_url})")

        rows.append((path, why, signals))
        if not signals:
            shareable.append(path)

    for path, why, signals in rows:
        print(f"• {path}   — {why}")
        if signals:
            for s in signals:
                print(f"    ⚠️  {s}")
        else:
            print("    ✅ لا فرق مقيس بين الحسابين")
        print()

    print("=== الحكم ===")
    if shareable:
        print(f"⚠️  مسارات بدون فرق مقيس: {shareable} — تستحق مراجعة القرار.")
        return 1
    print("✅ كل المسارات الخمسة تحمل بيانات مرتبطة بالمستخدم أو الجلسة —")
    print("   لا واحد منها صالح للمشاركة بكاش على مستوى الأصل. لذلك أُخرجت")
    print("   كلها من قائمة السماح، وبقيت أصول /static/ العامة فقط.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
