"""أداة البحث الخارجي (web_research): معلومة عامة بمصادرها، مفصولة عن بيانات
المزرعة، ومحجوبة عن أي مستخدم بدون صلاحية المساعد."""
from types import SimpleNamespace

from app.assistant import agent_tools, llm_bridge


def test_web_research_returns_answer_with_sources(app, monkeypatch):
    monkeypatch.setattr(llm_bridge, "grounded_search",
                        lambda q, lang="ar": {"answer": "حوالي 16%", "sources": [{"title": "t", "url": "https://x.y"}]})
    out = agent_tools.web_research("نسبة بروتين علف التسمين")
    assert out["status"] == "ok"
    assert out["origin"] == "external_web"
    assert out["sources"][0]["url"] == "https://x.y"


def test_web_research_unavailable_when_search_fails(app, monkeypatch):
    monkeypatch.setattr(llm_bridge, "grounded_search", lambda q, lang="ar": None)
    assert agent_tools.web_research("سؤال")["status"] == "unavailable"


def test_grounded_search_returns_none_without_key(app, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert llm_bridge.grounded_search("سؤال") is None


def test_tool_hidden_without_assistant_permission(app):
    user = SimpleNamespace(has_permission=lambda code: False)
    assert agent_tools.web_research not in agent_tools.build_tools_for_user(user)


def test_tool_available_with_assistant_permission(app):
    user = SimpleNamespace(has_permission=lambda code: code == "assistant.use")
    assert agent_tools.web_research in agent_tools.build_tools_for_user(user)


def test_system_prompt_forces_external_label_and_blocks_farm_data_use():
    prompt = llm_bridge.GEMINI_SYSTEM_PROMPT_TEMPLATE
    assert "حسب مصادر خارجية" in prompt
    assert "web_research" in prompt
