"""بند إضافي 150 — طلبك عبر ROADMAP.md: "نظام خيارات موحّدة ومترجمة
(قوائم أعراض/أنواع بلاغ قابلة للتوسيع من المالك)". قبل هذا البند، زر
"+" بشاشة "رفع بلاغ جديد" كان يضيف خياراً بالمتصفح فقط (جافاسكربت
بحت، يختفي بأول تحديث صفحة) بدل حفظه فعلياً — هذا يحوّل نوع البلاغ
لكتالوج حقيقي بنفس نمط UsageRoute/Breed/AnimalColor."""
from app.models import ReportType


def test_seed_defaults_creates_four_core_types(app):
    ReportType.seed_defaults()
    names = {r.name for r in ReportType.query.all()}
    assert {"مرض", "مشكلة", "صيانة", "أخرى"} <= names


def test_seed_defaults_is_idempotent(app):
    ReportType.seed_defaults()
    ReportType.seed_defaults()
    assert ReportType.query.count() == 4


def test_report_form_renders_types_from_catalog(logged_in_client):
    resp = logged_in_client.get("/team/reports/new")
    body = resp.get_data(as_text=True)
    assert 'value="مرض"' in body
    assert 'value="مشكلة"' in body
    # الجافاسكربت القديم (إضافة وهمية بالمتصفح بس) لازم يكون اختفى
    assert "newReportTypeInput" not in body


def test_add_new_report_type_persists_and_appears_in_form(logged_in_client):
    resp = logged_in_client.post("/team/reports/types/new", data={"name": "طارئ جوي"}, follow_redirects=True)
    assert resp.status_code == 200
    assert ReportType.query.filter_by(name="طارئ جوي").first() is not None

    form_resp = logged_in_client.get("/team/reports/new")
    assert 'value="طارئ جوي"' in form_resp.get_data(as_text=True)


def test_add_duplicate_report_type_rejected(logged_in_client):
    ReportType.seed_defaults()
    resp = logged_in_client.post("/team/reports/types/new", data={"name": "مرض"}, follow_redirects=True)
    assert resp.status_code == 200
    assert ReportType.query.filter_by(name="مرض").count() == 1
