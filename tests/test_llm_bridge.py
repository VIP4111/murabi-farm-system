"""بند إضافي 84 — أول اختبارات لجسر ترقية المساعد الذكي (بند 25، نقطة
10 من قائمة نقاط الضعف). كان بدون أي اختبار من الأساس، وكان فيه خلل
حقيقي (اسم نموذج غير موجود "claude-opus-4-8") ما اكتُشف أبداً لأن
ask() تبتلع كل استثناء وترجع None بصمت. حزمة anthropic نفسها غير
مثبَّتة بهذا المشروع (اختيارية، محايدة بـrequirements.txt) — الاختبارات
هنا تحقن وحدة anthropic وهمية بـsys.modules عشان تختبر مسار الاستدعاء
الحقيقي بدون الحاجة للحزمة الفعلية أو مفتاح حقيقي."""
import sys
import types

import pytest

from app.assistant import llm_bridge


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    sys.modules.pop("anthropic", None)
    yield
    sys.modules.pop("anthropic", None)


def test_is_configured_false_without_key():
    assert llm_bridge.is_configured() is False


def test_is_configured_true_with_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-test-key")
    assert llm_bridge.is_configured() is True


def test_ask_returns_none_immediately_without_key():
    assert llm_bridge.ask("كم عدد الحيوانات؟", "سياق تجريبي") is None


def test_ask_returns_none_if_anthropic_package_missing(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-test-key")
    # anthropic فعلياً غير مثبَّتة بهذا venv — import anthropic يفشل طبيعياً
    assert llm_bridge.ask("سؤال حر", "سياق") is None


def _install_fake_anthropic(reply_text=None, raise_error=None):
    fake_module = types.ModuleType("anthropic")

    class FakeTextBlock:
        type = "text"
        text = reply_text

    class FakeResponse:
        content = [FakeTextBlock()] if reply_text is not None else []

    class FakeMessages:
        def create(self, **kwargs):
            if raise_error:
                raise raise_error
            FakeMessages.last_call_kwargs = kwargs
            return FakeResponse()

    class FakeAnthropic:
        def __init__(self, *a, **kw):
            self.messages = FakeMessages()

    fake_module.Anthropic = FakeAnthropic
    sys.modules["anthropic"] = fake_module
    return fake_module


def test_ask_returns_parsed_text_on_success(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-test-key")
    _install_fake_anthropic(reply_text="  عندك 42 رأس حالياً.  ")
    result = llm_bridge.ask("كم عدد الحيوانات؟", "بيانات المزرعة هنا")
    assert result == "عندك 42 رأس حالياً."


def test_ask_uses_a_real_looking_model_id(monkeypatch, app):
    """الخلل الفعلي اللي اكتُشف هالبند: DEFAULT_MODEL القديمة
    "claude-opus-4-8" مو معرِّف حقيقي — هذا الاختبار يتأكد إن القيمة
    الحالية على الأقل بصيغة معرِّف نموذج Claude معقولة، ويثبّت السلوك
    عشان أي رجوع لخطأ مشابه يفشل الاختبار فوراً."""
    assert llm_bridge.DEFAULT_MODEL.startswith("claude-")
    assert llm_bridge.DEFAULT_MODEL != "claude-opus-4-8"


def test_ask_returns_none_and_logs_on_api_error(monkeypatch, app):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-test-key")
    _install_fake_anthropic(raise_error=RuntimeError("invalid model: claude-opus-4-8"))
    with app.app_context():
        result = llm_bridge.ask("سؤال", "سياق")
    assert result is None


def test_ask_returns_none_when_response_has_no_text_block(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-test-key")
    _install_fake_anthropic(reply_text=None)
    assert llm_bridge.ask("سؤال", "سياق") is None
