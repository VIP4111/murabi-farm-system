"""بند إصلاح (فحص عميق — طلبك: "افحص شاشة المساعد الذكي كمان") —
ملخص بطاقة اعتماد "الإدخال الذكي" (`summary_ar`) كان يُطلَب من Gemini
بالعربي دائماً بغض النظر عن لغة مُنشئ المسودة، رغم إن نفس الشخص
غالباً هو من يراجع بطاقة الاعتماد لاحقاً. صار يُطلَب بلغته الفعلية."""
from unittest.mock import patch

from app.extensions import db
from app.assistant import draft_action_service, llm_bridge
from app.models import Role, User


def _make_role_user(role_name, phone, lang="ar"):
    role = Role.query.filter_by(name=role_name).first()
    user = User(name=f"مستخدم {role_name}", phone=phone, role_id=role.id, language=lang)
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_draft_action_tool_requests_summary_in_english_for_english_lang(app):
    tool = llm_bridge._draft_action_tool("en")
    desc = tool.function_declarations[0].parameters.properties["summary_ar"].description
    assert "English" in desc


def test_draft_action_tool_requests_summary_in_arabic_by_default(app):
    tool = llm_bridge._draft_action_tool()
    desc = tool.function_declarations[0].parameters.properties["summary_ar"].description
    assert "العربية" in desc


def test_propose_from_text_passes_creator_language_to_parser(app):
    owner = _make_role_user("owner", "0500099801", lang="en")
    with patch("app.assistant.llm_bridge.parse_draft_action", return_value=None) as mock_parse:
        draft_action_service.propose_from_text("سجلت وزن اليوم للرأس 900: 35 كيلو", created_by=owner)
    mock_parse.assert_called_once()
    args, kwargs = mock_parse.call_args
    assert args[1] == "en" or kwargs.get("lang") == "en"
