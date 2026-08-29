"""بند إضافي 312 — طلبك "اكمل" (جولة تدقيق خامسة). فجوة حقيقية: مسودة
الصورة (بند 305) تحفظ رابطاً دائماً للصورة، بينما مسودة الصوت (بند
299) كانت تحلّل المقطع وترميه — صفر توثيق دائم. نفس مستوى الأدلة صار
بالاثنين، بإعادة استخدام `report_service.save_voice_note` الموجودة
أصلاً لملاحظات البلاغات الصوتية."""
import io
from unittest.mock import patch

from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.assistant import draft_action_service
from app.models import AssistantDraftAction


def _audio_file(name="note.webm", content=b"fake-audio-bytes"):
    return FileStorage(stream=io.BytesIO(content), filename=name, content_type="audio/webm")


def test_propose_from_audio_stores_audio_url(app, owner):
    draft = draft_action_service.propose_from_audio(
        b"bytes", "audio/webm", created_by=owner, audio_url="/uploads/audio/x.webm",
    )
    assert draft.audio_url == "/uploads/audio/x.webm"


def test_propose_from_audio_without_url_still_saves(app, owner):
    """رفع الصوت للتخزين اختياري — فشله ما يوقف التحليل أو حفظ المسودة."""
    draft = draft_action_service.propose_from_audio(b"bytes", "audio/webm", created_by=owner)
    assert draft.audio_url is None
    assert draft.id is not None


def test_drafts_new_voice_route_persists_audio_url(app, client, owner, monkeypatch):
    monkeypatch.delenv("CLOUDINARY_CLOUD_NAME", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})

    resp = client.post(
        "/assistant/drafts/new-voice",
        data={"audio": _audio_file()},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    draft = AssistantDraftAction.query.filter_by(input_source="voice").order_by(AssistantDraftAction.id.desc()).first()
    assert draft is not None
    assert draft.audio_url is not None
    assert draft.audio_url.startswith("/uploads/audio/")


def test_drafts_list_shows_audio_player_for_voice_drafts(app, client, owner):
    draft = AssistantDraftAction(
        raw_text="(مقطع صوتي)", input_source="voice", status="pending",
        created_by_id=owner.id, audio_url="/uploads/audio/sample.webm",
    )
    db.session.add(draft)
    db.session.commit()

    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    resp = client.get("/assistant/drafts", follow_redirects=True)
    assert b"/uploads/audio/sample.webm" in resp.data
