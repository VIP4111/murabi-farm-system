"""بند إضافي 128 — تعميم غلاف التمرير الأفقي (.table-scroll، بند 124)
على كل جدول متبقٍّ بالنظام كان بدونه (46 قالب) — منع تمدّد الصفحة
كلها أفقياً على الجوال، كل جدول يتمرّر لحاله داخل حدوده."""
import pathlib
import re

TEMPLATES_DIR = pathlib.Path(__file__).parent.parent / "app" / "templates"


def test_every_template_with_a_table_wraps_it_in_table_scroll():
    offenders = []
    for path in TEMPLATES_DIR.rglob("*.html"):
        text = path.read_text()
        if "<table" not in text:
            continue
        # كل ظهور لـ<table وقبله مباشرة (بأي مسافة بيضاء) نص "table-scroll"
        # ضمن آخر 60 حرف — فحص تقريبي كافٍ هنا (مو Jinja/HTML parser كامل).
        for m in re.finditer(r"<table\b", text):
            window = text[max(0, m.start() - 80):m.start()]
            if "table-scroll" not in window:
                offenders.append(str(path.relative_to(TEMPLATES_DIR)))
                break
    assert not offenders, f"جداول بدون غلاف .table-scroll: {offenders}"
