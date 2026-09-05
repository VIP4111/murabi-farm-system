"""SEC-01 — غلاف pytest لاختبار المتصفح الحقيقي.

فجوة القبول رقم 5: اختبار الثغرة الأساسي يجب ألا يبقى خارج كل تحقق آلي.
هنا يصير جزءاً من `pytest` العادي: **يعمل فعلياً** بأي بيئة فيها Playwright
وChromium (محلياً أو CI مجهَّز)، و**يُتخطّى بسبب صريح** حيث لا تتوفران —
لا يختفي بصمت. البديل الآلي الدائم بالـCI الحالي: `tests/js/sw.test.js`
(51 اختباراً على منطق الـSW) + `tests/test_sec01_sw_cache_isolation.py`.

التشغيل اليدوي الكامل بأمر واحد: `bash tests/e2e/run_sw_e2e.sh`
"""
import importlib.util
import os
import subprocess
import sys

import pytest

E2E_SCRIPT = os.path.join(os.path.dirname(__file__), "e2e", "run_sw_e2e.sh")


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _browser_available() -> bool:
    if not _has_module("playwright"):
        return False
    import glob
    return bool(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome")
                or glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/headless_shell")
                or os.environ.get("PLAYWRIGHT_BROWSERS_PATH"))


def _missing() -> str:
    """سبب التخطّي، أو نص فارغ لو كل شي متاح."""
    lacking = []
    if not _browser_available():
        lacking.append("Playwright/Chromium (pip install playwright && playwright install chromium)")
    # نفحص **الوحدة** لا الملف التنفيذي: داخل venv بلا تفعيل، `gunicorn`
    # ليس على PATH رغم أنه مثبَّت — وكان ذلك يتخطّى الاختبار دائماً بصمت.
    if not _has_module("gunicorn"):
        lacking.append("gunicorn")
    return "غير متوفر: " + "، ".join(lacking) if lacking else ""


requires_browser = pytest.mark.skipif(bool(_missing()), reason=_missing() or "متوفر")

# سيناريو المقارنة لا يحتاج متصفحاً إطلاقاً (urllib فقط) — يحتاج الخادم فقط،
# فشرط تخطّيه أضيق: لو gunicorn موجود يعمل حتى بلا Playwright.
requires_server = pytest.mark.skipif(
    not _has_module("gunicorn"), reason="غير متوفر: gunicorn")


def _run(scenario: str, expected: str):
    # نمرّر مفسّر بايثون الحالي للسكربت ليستخدم نفس الـvenv بلا تفعيل.
    env = {**os.environ, "PYTHON": sys.executable}
    proc = subprocess.run(["bash", E2E_SCRIPT, scenario], capture_output=True,
                          text=True, timeout=900, env=env)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    assert proc.returncode == 0, f"فشل سيناريو {scenario} — راجع المخرجات أعلاه"
    assert expected in proc.stdout, f"لم تظهر علامة النجاح {expected!r}"


@pytest.mark.e2e
@requires_browser
def test_sw_cache_isolation_in_a_real_browser():
    """مالك ⇒ خروج ⇒ عامل على سياق متصفح واحد (جهاز مشترك): لا شاشة
    حسّاسة تُخزَّن، الكاش يُمسح عند الخروج، الرد المتأخر لا يعيد بيانات
    المالك، ولا يُعرَض محتواه للعامل تحت انقطاع الشبكة."""
    _run("--isolation", "ISOLATED")


@pytest.mark.e2e
@requires_browser
def test_sw_upgrade_clears_contaminated_cache():
    """ترقية v7→v8 بكاش ملوّث وتبويبات مفتوحة تُزيل الكاش القديم بالكامل."""
    _run("--upgrade", "UPGRADE-CLEAN")


@pytest.mark.e2e
@requires_browser
def test_cache_purge_preserves_offline_submission_queue():
    """مسح الكاش لا يمسّ طابور الإدخالات غير المرسَلة (لا فقدان بيانات)،
    ولا يقع نَسْب خاطئ لإدخال المالك عند تبديل الحساب."""
    _run("--queue", "مسح الكاش لا يمسّ طابور الإدخالات")


@pytest.mark.e2e
@requires_server
def test_the_five_field_pages_all_carry_session_data():
    """دليل قرار قائمة السماح: المسارات الخمسة التي كانت مستثناة تختلف
    فعلياً بين حساب المالك وحساب العامل وتحمل اسم المستخدم ورموز CSRF
    مرتبطة بالجلسة — فلا واحد منها يصلح للمشاركة بكاش على مستوى الأصل.
    لو تغيّر ذلك مستقبلاً (صفحة صارت متطابقة فعلاً) يسقط هذا الاختبار
    فيُراجَع القرار بدل أن يبقى مبرَّراً بنصّ قديم."""
    _run("--diff", "لا واحد منها صالح للمشاركة بكاش على مستوى الأصل")
