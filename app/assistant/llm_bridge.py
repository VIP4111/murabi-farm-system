"""
جسر الترقية المستقبلية لـ Claude API (بند 25 — معمارية هجينة)، ومنذ
بند إضافي 297 جسر Gemini بأدوات القراءة الذكية (المرحلة ٢ من خطة "عقل
المزرعة"، الأرتيفاكت المعتمد).

المحرك المحلي (`nlu_service.py`) يغطي الأسئلة المتوقعة بمطابقة كلمات
مفتاحية على بيانات المزرعة الحية وقاعدة المعرفة. أي سؤال حر ما يطابق شي
محلياً يوصل هنا، بالترتيب: Gemini بأدوات القراءة (`ask_with_tools`) أولاً
لو `GEMINI_API_KEY` مفعَّل، وإلا Claude النصي القديم (`ask`) لو
`ANTHROPIC_API_KEY` مفعَّل، وإلا None (رد "لم أفهم سؤالك" من
`nlu_service.py`). كلاهما يبتلع كل استثناء ويرجع None بصمت عند أي فشل —
الرد المحلي يبقى دائماً شبكة أمان أخيرة.

**للترقية لاحقاً** (بدون أي تعديل على الواجهات، القوالب، أو الجداول):
1. أضف `ANTHROPIC_API_KEY=...` بملف `.env` بجذر المشروع.
2. ثبّت الحزمة: `pip install anthropic` وأضفها لـ requirements.txt.
هذا الملف هو نقطة الربط الوحيدة — كل شي ثاني بالنظام يبقى كما هو.
"""
import os

SYSTEM_PROMPT_TEMPLATE = """أنت المساعد الذكي لنظام "مربي" لإدارة مزرعة أغنام/ماعز/نعام. تخاطب المربي (صاحب المزرعة) أو أحد أفراد فريقه.

قواعد صارمة:
- {language_instruction}
- بإيجاز ووضوح، بدون مقدمات طويلة.
- اعتمد فقط على بيانات المزرعة الحية المرفقة أدناه وعلى قاعدة المعرفة التشغيلية المرفقة — لا تخترع أرقام أو أسماء حيوانات غير موجودة بالسياق المعطى.
- المساعد قرار مو طبيب: ممنوع اقتراح جرعة دواء أو تشخيص طبي نهائي لحيوان معيّن. أي قرار علاجي نهائي يحتاج الطبيب البيطري حصراً — وجّه المستخدم له عند الحاجة.
- لو السؤال خارج نطاق إدارة المزرعة تماماً، وضّح بأدب أنك مختص بشؤون المزرعة فقط.

بيانات المزرعة الحية الآن:
{context}
"""

# بند إضافي 275 — طلبك الصريح "كل شي دفعة وحدة" لدعم لغات متعددة.
# نفس مجموعة اللغات المدعومة أصلاً بالشاشات الميدانية (User.language).
_LANGUAGE_INSTRUCTIONS = {
    "ar": "جاوب بالعربي دايماً.",
    "en": "Always answer in English.",
    "am": "ሁልጊዜ በአማርኛ መልስ ስጥ።",
    "hi": "हमेशा हिंदी में उत्तर दें।",
}

# بند إضافي 84، 2026-08-02 — القيمة القديمة "claude-opus-4-8" مو معرِّف
# نموذج حقيقي إطلاقاً (خطأ كتابي من بند 25، ما اكتُشف لأن ask() يبتلع
# كل الاستثناءات ويرجع None بصمت — لو حد فعّل المفتاح، كانت كل محاولة
# تفشل بصمت وترجع لنفس "لم أفهم سؤالك" بدون أي مؤشر خطأ). صار
# claude-sonnet-5 (قدرة عالية وتكلفة معقولة، الافتراضي الموصى به حالياً).
DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")


def is_configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


# بند إضافي 297 — نظام Gemini بأدوات القراءة. نفس تعليمات
# SYSTEM_PROMPT_TEMPLATE أعلاه + تعليمتين إضافيتين حاسمتين للأدوات:
# (1) توضيح اللبس (تحسينك الأول المعتمد) — لا تخمين عند تعدد النتائج،
# (2) الأدوات "قراءة" بس، صفر تنفيذ فعلي بهذي المرحلة.
GEMINI_SYSTEM_PROMPT_TEMPLATE = """أنت المساعد الذكي لنظام "مربي" لإدارة مزرعة أغنام/ماعز/نعام. تخاطب المربي (صاحب المزرعة) أو أحد أفراد فريقه.

قواعد صارمة:
- {language_instruction}
- بإيجاز ووضوح، بدون مقدمات طويلة.
- استخدم الأدوات المتاحة لك للإجابة على أسئلة بيانات المزرعة الحية — لا تخترع أرقام أو أسماء حيوانات من عندك أبداً.
- لو أداة `search_animal_or_barn` رجعت "ambiguous" (تعدد نتائج)، توقف فوراً واسأل المستخدم يحدد المقصود بوضوح — ممنوع تخمين أول نتيجة أو أقربها.
- كل الأدوات المتاحة لك "قراءة" بس — ممنوع الادّعاء إنك سجّلت أو عدّلت أو حذفت أي شي بقاعدة البيانات، حتى لو طلب المستخدم ذلك؛ وضّح إنه هذي الميزة قادمة قريباً وتحتاج تأكيده الصريح أول.
- المساعد قرار مو طبيب: ممنوع اقتراح جرعة دواء أو تشخيص طبي نهائي لحيوان معيّن. أي قرار علاجي نهائي يحتاج الطبيب البيطري حصراً.
- لو السؤال خارج نطاق إدارة المزرعة تماماً، وضّح بأدب أنك مختص بشؤون المزرعة فقط.
"""

DEFAULT_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def is_gemini_configured() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY"))


def ask_with_tools(question: str, user, lang: str = "ar") -> str | None:
    """نفس فلسفة `ask()` بالضبط (None عند أي فشل أو غياب المفتاح، صفر
    استثناء يطلع لـ`nlu_service.py`) — بس بدل نص سياق ثابت مجمَّع مسبقاً،
    يعطي Gemini قائمة أدوات قراءة حقيقية (`agent_tools.build_tools_for_user`)
    يقرر بنفسه أيها يحتاج وينفّذها مباشرة (استدعاء تلقائي عبر SDK)."""
    if not is_gemini_configured():
        return None
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return None
    try:
        from app.assistant import agent_tools
        tools = agent_tools.build_tools_for_user(user)
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        language_instruction = _LANGUAGE_INSTRUCTIONS.get(lang, _LANGUAGE_INSTRUCTIONS["ar"])
        response = client.models.generate_content(
            model=DEFAULT_GEMINI_MODEL,
            contents=question,
            config=types.GenerateContentConfig(
                system_instruction=GEMINI_SYSTEM_PROMPT_TEMPLATE.format(language_instruction=language_instruction),
                tools=tools or None,
            ),
        )
        text = (response.text or "").strip()
        return text or None
    except Exception as e:
        try:
            from flask import current_app
            current_app.logger.warning("llm_bridge.ask_with_tools failed: %s", e)
        except Exception:
            pass
        return None


# بند إضافي 298 — المرحلة ٣ (دفتر ملاحظات المزرعة + RAG). نموذج تمثيل
# رقمي منفصل عن نموذج المحادثة أعلاه (نفس مفتاح `GEMINI_API_KEY`، خدمة
# مختلفة من نفس المزوّد).
DEFAULT_EMBEDDING_MODEL = os.environ.get("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")


def embed_text(text: str) -> list[float] | None:
    """يرجع التمثيل الرقمي (embedding) لنص واحد، أو None عند أي فشل أو
    غياب المفتاح — نفس فلسفة `ask()`/`ask_with_tools()` بالضبط، صفر
    استثناء يطلع لمن يستدعيها."""
    if not is_gemini_configured():
        return None
    try:
        from google import genai
    except ImportError:
        return None
    try:
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        response = client.models.embed_content(model=DEFAULT_EMBEDDING_MODEL, contents=text)
        embedding = response.embeddings[0]
        return list(embedding.values)
    except Exception as e:
        try:
            from flask import current_app
            current_app.logger.warning("llm_bridge.embed_text failed: %s", e)
        except Exception:
            pass
        return None


def ask(question: str, context_text: str, lang: str = "ar") -> str | None:
    """يرجع رد Claude، أو None لو المفتاح غير مُفعّل أو صار أي خطأ (نرجع
    None عمداً بدل رفع استثناء — nlu_service.py يلتف على fallback محلي).
    ``lang`` يحدد لغة رد Claude نفسه (بند إضافي 275)."""
    if not is_configured():
        return None
    try:
        import anthropic
    except ImportError:
        return None
    try:
        client = anthropic.Anthropic()
        language_instruction = _LANGUAGE_INSTRUCTIONS.get(lang, _LANGUAGE_INSTRUCTIONS["ar"])
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT_TEMPLATE.format(context=context_text, language_instruction=language_instruction),
            messages=[{"role": "user", "content": question}],
        )
        text = next((b.text for b in response.content if b.type == "text"), None)
        return text.strip() if text else None
    except Exception as e:
        # نبتلع الاستثناء عمداً (المستخدم يرجع لـfallback محلي سلس)، لكن
        # نسجّله بسجلات السيرفر — بدون هذا، خطأ إعداد حقيقي (مفتاح غلط،
        # اسم نموذج غلط زي الخطأ اللي اكتشفناه بند 84) يختفي بصمت للأبد
        # ومستحيل تشخيصه لاحقاً.
        try:
            from flask import current_app
            current_app.logger.warning("llm_bridge.ask failed: %s", e)
        except Exception:
            pass
        return None
