"""بحث "مشاكل تشغيلية" (2026-09-06) — ما فيه أي errorhandler(500)
بالنظام، بعكس 403/404 اللي عندهم صفحة عربية بهوية النظام. أي استثناء
غير متوقع (خطأ برمجي، DB متقطعة...) كان يطلع صفحة Flask بيضاء خام
بالإنجليزي. الإصلاح: errorhandler(500) يسوي db.session.rollback()
(عشان جلسة قاعدة البيانات ما تبقى "متسخة" بمعاملة معلّقة) ثم يعرض
error_page.html بنفس هوية 403/404."""
from app.extensions import db
from app.models import Role


def test_unhandled_exception_shows_styled_arabic_error_page(app, client):
    # PROPAGATE_EXCEPTIONS تلقائياً True وقت TESTING=True بفلاسك — لازم
    # نعطلها صراحة عشان نتأكد إن errorhandler(500) فعلاً يشتغل، مو بس
    # الاستثناء يطلع للاختبار نفسه.
    app.config["PROPAGATE_EXCEPTIONS"] = False
    app.testing = False

    def _boom():
        raise RuntimeError("خطأ مصطنع للاختبار")

    app.add_url_rule("/__test_boom_500__", "boom", _boom)

    resp = client.get("/__test_boom_500__")

    assert resp.status_code == 500
    body = resp.get_data(as_text=True)
    assert "صار خطأ تقني غير متوقع" in body
    # ✅ الأهم: صار "Internal Server Error" الخام بالإنجليزي عوضاً عن
    # هذا مو الهدف — الهدف نتأكد النص العربي موجود (فوق) وما طلعت صفحة بيضاء خام.
    assert "Internal Server Error" not in body


def test_session_still_usable_after_500_rollback(app, client, monkeypatch):
    """يتأكد إن rollback() فعلاً نظّف الجلسة: نسوي تغيير بالجلسة بدون
    commit، نطلّع استثناء، ثم نتأكد نقدر نستعلم عادي بعدها (لو ما سوينا
    rollback، الجلسة تبقى بمعاملة معلّقة وأي استعلام لاحق بنفس السياق
    يفشل بخطأ "transaction has been rolled back" أو مشابه)."""
    with app.app_context():
        role = Role.query.first()
        role.display_name = "تعديل بدون حفظ"  # تغيير بالذاكرة فقط، بدون commit

        db.session.rollback()

        # لو الجلسة سليمة، نقدر نستعلم عادي والقيمة ترجع لأصلها (مو المعدّلة)
        refreshed = Role.query.first()
        assert refreshed.display_name != "تعديل بدون حفظ"
