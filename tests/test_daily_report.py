"""التقرير اليومي (بند إضافي، طلبك الصريح: "ابي كل عامل يدخل...
ويكتب التقرير اليومي ويرسله... هو يرسله بلغته وأنا يوصلني بالعربي").
اختبارات بدون Gemini فعلي (المفتاح غير مضبوط بالاختبارات) — نتأكد من
سلوك عدم توفر الترجمة (يرجع None بأمان، النص الأصلي يبقى معروضاً)،
ومن منطق "تقرير واحد باليوم" والتقييد لصاحب الحلال."""
from unittest.mock import patch

from app.extensions import db
from app.models import DailyReport, Role, User
from app.team import daily_report_service as svc


def _worker(phone, role_name="worker", language="ar"):
    role = Role.query.filter_by(name=role_name).first()
    u = User(name=f"مستخدم {phone}", phone=phone, role_id=role.id, language=language)
    u.set_password("pass1234")
    db.session.add(u)
    db.session.commit()
    return u


def test_arabic_author_no_translation_call_needed(app, owner):
    report = svc.submit_or_update(author=owner, text="اليوم سويت جولة على الحظائر")
    assert report.arabic_text == "اليوم سويت جولة على الحظائر"
    assert report.author_lang == "ar"


def test_non_arabic_author_translated_via_gemini(app):
    worker = _worker("0500099001", language="en")
    with patch("app.assistant.llm_bridge.translate_to_arabic", return_value="قمت بتنظيف الحظيرة اليوم"):
        report = svc.submit_or_update(author=worker, text="I cleaned the barn today")
    assert report.author_text == "I cleaned the barn today"
    assert report.arabic_text == "قمت بتنظيف الحظيرة اليوم"
    assert report.display_text() == "قمت بتنظيف الحظيرة اليوم"


def test_translation_unavailable_falls_back_to_original_text(app):
    """Gemini غير مفعَّل بالاختبارات — `translate_to_arabic` يرجع None
    فعلاً (بدون mock)، والتقرير يُحفَظ بنجاح مع `arabic_text=None`،
    و`display_text()` يعرض النص الأصلي بدل ما يفشل الحفظ كامل."""
    worker = _worker("0500099002", language="en")
    report = svc.submit_or_update(author=worker, text="I fed the animals")
    assert report.arabic_text is None
    assert report.display_text() == "I fed the animals"


def test_second_submission_same_day_updates_not_duplicates(app, owner):
    first = svc.submit_or_update(author=owner, text="تقرير الصباح")
    second = svc.submit_or_update(author=owner, text="تحديث المساء")
    assert first.id == second.id
    assert DailyReport.query.filter_by(author_id=owner.id).count() == 1
    assert DailyReport.query.get(first.id).author_text == "تحديث المساء"


def test_daily_report_form_accessible_to_any_logged_in_member(app, client):
    worker = _worker("0500099003")
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.post("/team/daily-report", data={"text": "شغلت اليوم على تنظيف المعالف"},
                        follow_redirects=True)
    assert resp.status_code == 200
    assert DailyReport.query.filter_by(author_id=worker.id).first() is not None


def test_daily_reports_list_forbidden_for_non_owner(app, client):
    worker = _worker("0500099004")
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.get("/team/daily-reports")
    assert resp.status_code == 403


def test_daily_reports_list_visible_to_owner(app, logged_in_client, owner):
    svc.submit_or_update(author=owner, text="تقرير صاحب الحلال نفسه")
    resp = logged_in_client.get("/team/daily-reports")
    assert resp.status_code == 200
    assert "تقرير صاحب الحلال نفسه".encode() in resp.data
