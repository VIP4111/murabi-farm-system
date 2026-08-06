"""بند إضافي 128 (تكملة) — توحيد أزرار "خطر" (حذف/تعطيل/إجهاض...) على
كلاس `.btn.danger` الموحّد (بند 124) بدل تكرار `style="background:#a32d2d"`
يدوياً بكل قالب — 6 مواضع كانت لسا على النمط القديم. اختبار حراسة يمنع
رجوع النمط اليدوي مستقبلاً."""
import pathlib

TEMPLATES_DIR = pathlib.Path(__file__).parent.parent / "app" / "templates"


def test_no_template_hardcodes_danger_button_color_inline():
    offenders = []
    for path in TEMPLATES_DIR.rglob("*.html"):
        text = path.read_text()
        if "background:#a32d2d" in text or "background: #a32d2d" in text:
            offenders.append(str(path.relative_to(TEMPLATES_DIR)))
    assert not offenders, f"أزرار لسا تستخدم لون الخطر يدوياً بدل .btn.danger: {offenders}"
