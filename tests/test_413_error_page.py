"""بحث "مشاكل تشغيلية" (2026-09-06، جزء ثاني) — نفس نمط مشكلة 500: ما
فيه errorhandler(413) رغم إن MAX_CONTENT_LENGTH مضبوط (10MB). أي رفع
ملف (صورة بلاغ، ملاحظة صوتية...) أكبر من الحد يطلع صفحة Flask بيضاء
خام "413 Request Entity Too Large" بدل رسالة عربية مفهومة."""


def test_oversized_upload_shows_styled_arabic_error_page(app, client):
    from flask import request

    app.config["MAX_CONTENT_LENGTH"] = 10  # بايتات قليلة جداً عشان أي جسم طلب يتجاوزها بسهولة

    def _read_body():
        request.get_data()  # قراءة الجسم فعلياً هي اللي تُشغّل فحص MAX_CONTENT_LENGTH بفلاسك
        return "ok"

    app.add_url_rule(
        "/__test_upload_413__",
        "test_upload_413",
        _read_body,
        methods=["POST"],
    )

    resp = client.post("/__test_upload_413__", data=b"x" * 1000, content_type="application/octet-stream")

    assert resp.status_code == 413
    body = resp.get_data(as_text=True)
    assert "الملف كبير جداً" in body
    assert "Request Entity Too Large" not in body
