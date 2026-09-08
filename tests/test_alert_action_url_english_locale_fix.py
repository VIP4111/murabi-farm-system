"""بند إصلاح (طلبك، صورة حية: زر "حل المشكلة" يطلع بالعربي، بالإنجليزي
ما يطلع إطلاقاً) — `alert_action_url` كان يطابق `alert["category"]`
(نص مترجَم فوراً وقت البناء) مع مفاتيح عربية ثابتة بـ`_ALERT_ACTION_ROUTES`
— لحساب إنجليزي، `category` يصير إنجليزياً وما يطابق أي مفتاح، فالزر
يختفي بصمت لكل أنواع التنبيهات تقريباً، مو بس "بيانات ناقصة". الإصلاح:
مفتاح ثابت منفصل `category_key` غير قابل للترجمة."""
from app.extensions import db
from app.core import alerts_service
from app.assistant import context_service
from flask_babel import force_locale
from tests.factories import make_animal


def test_incomplete_data_alert_has_action_url_in_english_locale(app):
    animal = make_animal(animal_no="EN-ALERT-1", breed="عام/غير محدد")
    animal.gender = None  # يجعلها ناقصة البيانات
    db.session.commit()
    with app.test_request_context("/"), force_locale("en"):
        alerts = alerts_service._incomplete_animal_data()
        assert alerts
        alert = alerts[0]
        assert alert["category_key"] == "incomplete_animal_data"
        url = alerts_service.alert_action_url(alert)
        assert url is not None
        assert f"/animals/{animal.id}/edit" in url or "edit" in url


def test_alert_action_url_stable_across_locales(app):
    """نفس التنبيه (نفس category_key) لازم يرجّع نفس الرابط بغض النظر
    عن لغة العرض الحالية — الرابط لا يعتمد على الترجمة."""
    alert = {"category_key": "open_disease", "animal_id": 1}
    with app.test_request_context("/"), force_locale("ar"):
        with_ar = alerts_service.alert_action_url(alert)
    with app.test_request_context("/"), force_locale("en"):
        with_en = alerts_service.alert_action_url(alert)
    assert with_ar == with_en
    assert with_ar is not None


def test_vaccinations_due_summary_counts_regardless_of_locale(app):
    with force_locale("en"):
        summary_en = context_service.vaccinations_due_summary()
    with force_locale("ar"):
        summary_ar = context_service.vaccinations_due_summary()
    assert summary_en["count"] == summary_ar["count"]
