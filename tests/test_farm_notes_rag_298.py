"""بند إضافي 298 — المرحلة ٣ من خطة "عقل المزرعة": دفتر ملاحظات المزرعة
+ استرجاع دلالي (RAG) بتصفية مسبقة (تحسينك الثاني المعتمد: حظيرة/رأس/
وسم قبل حساب التشابه)."""
from unittest.mock import patch, MagicMock

from app.extensions import db
from app.assistant import agent_tools, farm_note_service, llm_bridge
from app.models import Role, User, FarmNote, FarmNoteEmbedding
from factories import make_animal, make_barn


def _make_role_user(role_name, phone):
    role = Role.query.filter_by(name=role_name).first()
    user = User(name=f"مستخدم {role_name}", phone=phone, role_id=role.id, language="ar")
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


# ---- create_note / embed_note ----

def test_create_note_saves_even_without_gemini_key(app, owner, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    note = farm_note_service.create_note(body="ملاحظة تجريبية", created_by=owner)
    assert note.id is not None
    assert FarmNoteEmbedding.query.filter_by(note_id=note.id).first() is None


def test_create_note_embeds_when_gemini_configured(app, owner, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    with patch("app.assistant.llm_bridge.embed_text", return_value=[0.1, 0.2, 0.3]):
        note = farm_note_service.create_note(body="إسهال متكرر بالحظيرة الشرقية", created_by=owner)
    embedding = FarmNoteEmbedding.query.filter_by(note_id=note.id).first()
    assert embedding is not None
    assert embedding.get_vector() == [0.1, 0.2, 0.3]


def test_embed_note_updates_existing_embedding(app, owner, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    with patch("app.assistant.llm_bridge.embed_text", return_value=[1.0, 0.0]):
        note = farm_note_service.create_note(body="نص أول", created_by=owner)
    with patch("app.assistant.llm_bridge.embed_text", return_value=[0.0, 1.0]):
        farm_note_service.embed_note(note)
    embedding = FarmNoteEmbedding.query.filter_by(note_id=note.id).first()
    assert embedding.get_vector() == [0.0, 1.0]


# ---- search_notes: تصفية مسبقة + تشابه ----

def test_search_pre_filters_by_barn_before_similarity(app, owner, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    barn_a = make_barn(barn_no="B-A", barn_name="حظيرة أ")
    barn_b = make_barn(barn_no="B-B", barn_name="حظيرة ب")

    with patch("app.assistant.llm_bridge.embed_text", return_value=[1.0, 0.0]):
        farm_note_service.create_note(body="ملاحظة عن حظيرة أ", created_by=owner, barn_id=barn_a.id)
        farm_note_service.create_note(body="ملاحظة عن حظيرة ب", created_by=owner, barn_id=barn_b.id)

    with patch("app.assistant.llm_bridge.embed_text", return_value=[1.0, 0.0]):
        results = farm_note_service.search_notes("أي موضوع", barn_id=barn_a.id)
    assert len(results) == 1
    assert results[0]["barn_name"] == "حظيرة أ"


def test_search_returns_most_similar_first(app, owner, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    with patch("app.assistant.llm_bridge.embed_text", return_value=[1.0, 0.0]):
        farm_note_service.create_note(body="مطابقة تماماً", created_by=owner)
    with patch("app.assistant.llm_bridge.embed_text", return_value=[0.0, 1.0]):
        farm_note_service.create_note(body="غير مطابقة إطلاقاً", created_by=owner)

    with patch("app.assistant.llm_bridge.embed_text", return_value=[1.0, 0.0]):
        results = farm_note_service.search_notes("سؤال")
    assert results[0]["body"] == "مطابقة تماماً"
    assert results[0]["similarity"] > results[1]["similarity"]


def test_search_returns_empty_without_gemini_key(app, owner, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    farm_note_service.create_note(body="ملاحظة", created_by=owner)
    assert farm_note_service.search_notes("سؤال") == []


def test_search_ignores_notes_without_embedding(app, owner, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)  # وقت الإنشاء بدون مفتاح
    farm_note_service.create_note(body="ملاحظة بدون تمثيل رقمي", created_by=owner)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    with patch("app.assistant.llm_bridge.embed_text", return_value=[1.0, 0.0]):
        assert farm_note_service.search_notes("سؤال") == []


# ---- أداة search_farm_notes بالصلاحيات ----

def test_search_farm_notes_tool_requires_animals_view_permission(app):
    worker = _make_role_user("worker", "0599999190")
    tools = agent_tools.build_tools_for_user(worker)
    assert agent_tools.search_farm_notes not in tools


def test_search_farm_notes_tool_available_for_doctor(app):
    doctor = _make_role_user("doctor", "0599999191")
    tools = agent_tools.build_tools_for_user(doctor)
    assert agent_tools.search_farm_notes in tools


def test_search_farm_notes_resolves_barn_name_and_animal_no(app, owner, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    barn = make_barn(barn_no="B-X", barn_name="حظيرة الحوامل")
    animal = make_animal(animal_no="Z-1", barn_id=barn.id)
    with patch("app.assistant.llm_bridge.embed_text", return_value=[1.0, 0.0]):
        farm_note_service.create_note(body="ملاحظة عن الرأس", created_by=owner, animal_id=animal.id)

    with patch("app.assistant.llm_bridge.embed_text", return_value=[1.0, 0.0]):
        result = agent_tools.search_farm_notes("سؤال", animal_no="Z-1")
    assert result["status"] == "found"
    assert result["notes"][0]["animal_no"] == "Z-1"


def test_search_farm_notes_not_found_message(app, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = agent_tools.search_farm_notes("سؤال ما له علاقة بشي")
    assert result["status"] == "not_found"


def test_search_farm_notes_ambiguous_barn_name_asks_for_clarification(app):
    """بند إضافي 309 — فجوة حقيقية: كانت تاخذ أول حظيرة تطابق جزئياً
    بصمت (نفس فئة التخمين اللي search_animal_or_barn بُنيت أصلاً
    (بند 297) عشان تمنعها). لازم تتوقف وتطلب توضيح مثلها بالضبط."""
    make_barn(barn_no="B-1", barn_name="حظيرة الحوامل الشرقية")
    make_barn(barn_no="B-2", barn_name="حظيرة الحوامل الغربية")
    result = agent_tools.search_farm_notes("سؤال", barn_name="حظيرة الحوامل")
    assert result["status"] == "ambiguous"
    assert len(result["candidates"]) == 2


# ---- صلاحية كتابة الملاحظة (الشاشة) ----

def test_farm_notes_route_requires_permission(app, client):
    worker = _make_role_user("worker", "0599999192")
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.get("/assistant/farm-notes")
    assert resp.status_code == 403


def test_owner_can_add_farm_note_via_route(app, client, owner):
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    resp = client.post("/assistant/farm-notes/new", data={"body": "ملاحظة من الشاشة"}, follow_redirects=True)
    assert resp.status_code == 200
    assert FarmNote.query.filter_by(body="ملاحظة من الشاشة").first() is not None
