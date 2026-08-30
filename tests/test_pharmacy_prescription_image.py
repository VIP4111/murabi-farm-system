"""بند إضافي (2026-08-30) — طلبك الصريح: "رفع روشتة دواء للمساعد الذكي
وتعبئة البيانات تلقائيًا. بعد ما يعبيها ارجع ادقق وحفضها." تعبئة مسبقة
بس لفورم "دواء جديد" الحقيقي — صفر كتابة مباشرة لقاعدة البيانات من
تحليل الصورة نفسه؛ صاحب الحلال/الدكتور يراجع ويحفظ بنفسه."""
import io
from unittest.mock import patch

from werkzeug.datastructures import FileStorage

from app.assistant import llm_bridge
from app.models import Pharmacy


def _image_file(name="rx.jpg"):
    return FileStorage(stream=io.BytesIO(b"fake-image-bytes"), filename=name, content_type="image/jpeg")


def test_prescription_image_extracts_and_prefills_form_without_saving(app, logged_in_client):
    """أهم فحص: التحليل يملأ الفورم بس — صفر صف Pharmacy جديد يُنشأ
    مباشرة من رفع الصورة."""
    extracted = {
        "name": "دواء من روشتة", "medicine_class": "antibiotic",
        "usage_method": "حقن عضل", "standard_dosage_note": "5 مل لكل رأس",
        "expiry_date": "2027-01-01", "withdrawal_days": 7, "withdrawal_days_milk": 2,
        "notes": None,
    }
    with patch.object(llm_bridge, "parse_pharmacy_prescription_image", return_value=extracted):
        resp = logged_in_client.post("/health/pharmacy/prescription-image",
                                      data={"image": _image_file()},
                                      content_type="multipart/form-data", follow_redirects=True)
    assert resp.status_code == 200
    assert Pharmacy.query.filter_by(name="دواء من روشتة").count() == 0
    body = resp.data.decode()
    assert "دواء من روشتة" in body
    assert "من الصورة" in body


def test_prescription_image_analysis_failure_shows_clear_error(app, logged_in_client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    resp = logged_in_client.post("/health/pharmacy/prescription-image",
                                  data={"image": _image_file()},
                                  content_type="multipart/form-data", follow_redirects=True)
    assert resp.status_code == 200
    assert "تعذّر تحليل الصورة".encode() in resp.data


def test_prescription_image_rejects_invalid_medicine_class_from_model():
    """حاجز حقيقي: لو الموديل رجّع فئة دواء مو من القائمة المغلقة
    المسموحة، نرفضها هنا بدل ما توصل كخيار قابل للتعبئة."""
    fake_json = '{"name": "دواء", "medicine_class": "اختراع_غير_موجود", "usage_method": null, ' \
                '"standard_dosage_note": null, "expiry_date": null, "withdrawal_days": null, ' \
                '"withdrawal_days_milk": null, "notes": null}'

    class FakeResponse:
        text = fake_json

    class FakeModels:
        def generate_content(self, **kwargs):
            return FakeResponse()

    class FakeClient:
        def __init__(self, api_key):
            self.models = FakeModels()

    import os
    os.environ["GEMINI_API_KEY"] = "fake-key"
    with patch("google.genai.Client", FakeClient):
        result = llm_bridge.parse_pharmacy_prescription_image(b"bytes", "image/jpeg")
    assert result is not None
    assert result["medicine_class"] is None
    assert result["name"] == "دواء"


def test_no_file_uploaded_redirects_with_error(app, logged_in_client):
    resp = logged_in_client.post("/health/pharmacy/prescription-image", data={},
                                  content_type="multipart/form-data", follow_redirects=True)
    assert resp.status_code == 200
    assert "ارفع صورة أولاً".encode() in resp.data


def test_worker_without_pharmacy_manage_permission_forbidden(app, client, worker):
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.post("/health/pharmacy/prescription-image", data={"image": _image_file()},
                        content_type="multipart/form-data")
    assert resp.status_code == 403
