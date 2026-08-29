"""بند إضافي 305 — طلبك: "دعم مرفقات الصور (Multimodal Input / Vision)"
بمحادثة المساعد الذكي. صورة تروح مباشرة لـGemini بالرؤية، بدون محرك
النيات المحلي أو قاعدة المعرفة (نص بس، ما يفهمان صوراً)."""
import io
from unittest.mock import patch, MagicMock

from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.assistant import llm_bridge, nlu_service
from app.models import AssistantMessage


def _image_file(name="test.jpg", content=b"\xff\xd8\xff" + b"x" * 100):
    return FileStorage(stream=io.BytesIO(content), filename=name, content_type="image/jpeg")


# ---- llm_bridge.ask_with_image ----

def test_ask_with_image_returns_none_without_gemini_key(app, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert llm_bridge.ask_with_image("وش هذا؟", b"fake-bytes", "image/jpeg") is None


def test_ask_with_image_returns_gemini_text_when_configured(app, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    fake_response = MagicMock(text="يبدو فيه احمرار بسيط بالجلد.")
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_response
    with patch("google.genai.Client", return_value=fake_client):
        reply = llm_bridge.ask_with_image("وش رأيك بهذي الحالة؟", b"fake-bytes", "image/jpeg")
    assert reply == "يبدو فيه احمرار بسيط بالجلد."


def test_ask_with_image_swallows_exceptions(app, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    with patch("google.genai.Client", side_effect=RuntimeError("network down")):
        assert llm_bridge.ask_with_image("وش هذا؟", b"fake-bytes", "image/jpeg") is None


# ---- nlu_service.answer_with_image / ask_and_record_with_image ----

def test_answer_with_image_uses_vision_reply(app, owner, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    with patch("app.assistant.llm_bridge.ask_with_image", return_value="وصف الصورة"):
        result = nlu_service.answer_with_image(owner, "وش هذا؟", b"bytes", "image/jpeg")
    assert result["reply"] == "وصف الصورة"
    assert result["answered_by"] == "llm_vision"


def test_answer_with_image_clear_message_without_gemini(app, owner, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = nlu_service.answer_with_image(owner, "وش هذا؟", b"bytes", "image/jpeg")
    assert "GEMINI_API_KEY" in result["reply"]
    assert result["answered_by"] == "local"


def test_ask_and_record_with_image_saves_image_url_on_user_message(app, owner, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    with patch("app.assistant.llm_bridge.ask_with_image", return_value="وصف الصورة"):
        nlu_service.ask_and_record_with_image(owner, "وش هذا؟", b"bytes", "image/jpeg", "/uploads/x.jpg")

    user_msg = AssistantMessage.query.filter_by(user_id=owner.id, role="user").first()
    assistant_msg = AssistantMessage.query.filter_by(user_id=owner.id, role="assistant").first()
    assert user_msg.image_url == "/uploads/x.jpg"
    assert assistant_msg.content == "وصف الصورة"
    assert assistant_msg.answered_by == "llm_vision"


def test_ask_and_record_with_image_defaults_content_when_no_text(app, owner, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    nlu_service.ask_and_record_with_image(owner, "", b"bytes", "image/jpeg", "/uploads/y.jpg")
    user_msg = AssistantMessage.query.filter_by(user_id=owner.id, role="user").first()
    assert user_msg.content  # نص افتراضي غير فاضٍ


# ---- الراوت ----

def test_send_route_with_image_creates_messages(app, client, owner, monkeypatch):
    monkeypatch.delenv("CLOUDINARY_CLOUD_NAME", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})

    with patch("app.assistant.llm_bridge.ask_with_image", return_value="تحليل الصورة"):
        resp = client.post(
            "/assistant/send",
            data={"message": "وش هذا؟", "image": _image_file()},
            content_type="multipart/form-data",
        )
    assert resp.status_code == 200
    assert resp.get_json()["reply"] == "تحليل الصورة"
    user_msg = AssistantMessage.query.filter_by(user_id=owner.id, role="user").order_by(AssistantMessage.id.desc()).first()
    assert user_msg.image_url is not None


def test_send_route_rejects_oversized_image(app, client, owner):
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    big_file = _image_file(content=b"x" * (9 * 1024 * 1024))
    resp = client.post(
        "/assistant/send",
        data={"message": "", "image": big_file},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
