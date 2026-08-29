"""بند إضافي 302 — طلبك: "ابي اذكى اصناعي يقترح عليه المهام ودكتور
يرفع تقرير". الذكاء الاصطناعي يقترح بس (من قائمة مسموحة، مفلترة صراحة)
— صاحب الحلال يراجع/يعدّل قبل التوزيع الفعلي، نفس مبدأ اقتراح ثم
اعتماد بشري بكل الخطة."""
from unittest.mock import patch, MagicMock

from app.extensions import db
from app.assistant import llm_bridge
from app.team import task_service
from factories import make_animal


PRESETS = task_service.ANIMAL_CHECKUP_ITEM_PRESETS


def test_suggest_returns_none_without_gemini_key(app, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert llm_bridge.suggest_checkup_items("سياق", PRESETS) is None


def test_suggest_filters_out_invented_items_not_in_allowed_list(app, monkeypatch):
    """الحاجز الحقيقي: حتى لو النموذج (محاكى) رجّع بند مو موجود
    بالقائمة، ما يوصل أبداً لقائمة الاقتراح النهائية."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    fake_response = MagicMock(text='{"items": ["فحص الحرارة والنبض", "بند مخترع غير موجود"], "reason": "سبب"}')
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_response
    with patch("google.genai.Client", return_value=fake_client):
        result = llm_bridge.suggest_checkup_items("سياق", PRESETS)
    assert result["items"] == ["فحص الحرارة والنبض"]
    assert "بند مخترع" not in result["items"]


def test_suggest_returns_none_when_all_items_invented(app, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    fake_response = MagicMock(text='{"items": ["بند غير موجود إطلاقاً"], "reason": "سبب"}')
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_response
    with patch("google.genai.Client", return_value=fake_client):
        result = llm_bridge.suggest_checkup_items("سياق", PRESETS)
    assert result is None


def test_suggest_handles_markdown_wrapped_json(app, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    fake_response = MagicMock(text='```json\n{"items": ["فحص الشهية والحالة العامة"], "reason": "لا مؤشرات خاصة"}\n```')
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_response
    with patch("google.genai.Client", return_value=fake_client):
        result = llm_bridge.suggest_checkup_items("سياق", PRESETS)
    assert result["items"] == ["فحص الشهية والحالة العامة"]


def test_suggest_returns_none_on_invalid_json(app, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    fake_response = MagicMock(text="مو JSON إطلاقاً")
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_response
    with patch("google.genai.Client", return_value=fake_client):
        assert llm_bridge.suggest_checkup_items("سياق", PRESETS) is None


# ---- الراوت ----

def test_checkup_suggest_route_prefills_page_with_suggested_items(app, client, owner, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    animal = make_animal(animal_no="500")
    fake_response = MagicMock(text='{"items": ["فحص الحرارة والنبض"], "reason": "تنبيه نشط"}')
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_response

    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    with patch("google.genai.Client", return_value=fake_client):
        resp = client.post(f"/animals/{animal.id}/checkup-suggest", follow_redirects=True)
    assert resp.status_code == 200
    assert "فحص الحرارة والنبض".encode() in resp.data
    assert "checked".encode() in resp.data


def test_checkup_suggest_route_without_gemini_flashes_error(app, client, owner, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    animal = make_animal(animal_no="501")
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    resp = client.post(f"/animals/{animal.id}/checkup-suggest", follow_redirects=True)
    assert resp.status_code == 200
    assert "الاقتراح الذكي غير متاح".encode() in resp.data


def test_checkup_suggest_route_requires_permission(app, client):
    from app.models import Role, User
    worker_role = Role.query.filter_by(name="worker").first()
    worker = User(name="عامل اختبار", phone="0599999220", role_id=worker_role.id)
    worker.set_password("pass1234")
    db.session.add(worker)
    db.session.commit()
    animal = make_animal(animal_no="502")

    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.post(f"/animals/{animal.id}/checkup-suggest")
    assert resp.status_code == 403
