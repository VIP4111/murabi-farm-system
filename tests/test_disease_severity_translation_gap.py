"""بند إصلاح — نفس فئة فجوة "open" بدفعات البيع: شاشة تسجيل مرض
(health/disease_form.html وbulk_action_form.html) تخزّن قيمة "الشدة"
كرمز إنجليزي ثابت (light/medium/severe) بـ`Disease.severity`، وكذا
3 شاشات كانت تعرضها خام بدون ترجمة: health/diseases_list.html،
health/dashboard.html، animal_detail.html."""
from tests.factories import make_animal


def test_ar_severity_filter_translates_codes():
    from app import create_app
    app = create_app()
    with app.app_context():
        ar_severity = app.jinja_env.filters["ar_severity"]
        assert str(ar_severity("light")) == "بسيطة"
        assert str(ar_severity("medium")) == "متوسطة"
        assert str(ar_severity("severe")) == "شديدة"
        # قيمة غير معروفة (بيانات قديمة عربية مثلاً) ترجع كما هي بدون كسر
        assert str(ar_severity("شديدة")) == "شديدة"


def test_diseases_list_shows_translated_severity_not_raw_code(app, logged_in_client):
    a = make_animal(animal_no="SEV-TR-01")
    resp = logged_in_client.post(f"/health/diseases/new", data={
        "animal_id": a.id, "disease_name": "مرض اختبار الترجمة",
        "date": "2026-01-01", "severity": "light",
    })
    assert resp.status_code in (302, 200)

    resp = logged_in_client.get("/health/diseases")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert ">light<" not in body
    assert "بسيطة" in body
