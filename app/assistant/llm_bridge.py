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

# بند إضافي 300 — "gemini-2.5-flash" (القيمة الأصلية ببند 297) صار
# موقوفاً لمستخدمين جدد (404 NOT_FOUND فعلي على الإنتاج، 2026-08-29 —
# نفس فئة خطأ اسم النموذج القديم ببند 84 مع Claude، بس هذي المرة
# اكتُشف بسرعة بسبب تسجيل `current_app.logger.warning` بدل الابتلاع
# الصامت). "gemini-3.6-flash" هو البديل الرسمي المذكور برسالة الخطأ
# نفسها من Google.
DEFAULT_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")


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


# ============================================================
# بند إضافي 299 — المرحلة ٤ (الأخيرة) من خطة "عقل المزرعة": الإدخال
# الذكي بالنص/الصوت. النموذج يقترح مسودة إجراء منظَّمة بس — التنفيذ
# الفعلي بقاعدة البيانات يصير حصرياً بعد اعتماد بشري صريح
# (`app/assistant/draft_action_service.py`)، هذا الملف لا يكتب أي شي
# بقاعدة البيانات إطلاقاً.
# ============================================================

# قائمة أنواع الإجراءات المسموح اقتراحها — **مصدر الحقيقة الوحيد**،
# نفس القائمة بالضبط لازم تطابق `draft_action_service.ALLOWED_ACTION_TYPES`
# (فحص تطابق موجود باختبار مخصَّص). أي نوع إجراء مو بهذي القائمة يُرفض
# قطعياً، بغض النظر عمّا يحاول النموذج يقترحه.
ALLOWED_DRAFT_ACTION_TYPES = ("register_birth", "record_weight")

# بند إضافي 299، تحسينك الرابع المعتمد — حاجز صلب صريح، مستقل تماماً عن
# تعليمات النظام النصية للنموذج (اللي ممكن يُخترق أو يُتجاوَز بصياغة
# ملتوية بالسؤال). هذا الفحص برمجي بحت، ما يعتمد على "طاعة" النموذج
# للتعليمات — أي مسودة تلمس جرعة دواء أو حذف سجل تُرفض هنا قطعياً قبل
# ما توصل لأي مستخدم للاعتماد، بغض النظر عن نوع الإجراء أو محتوى النص.
BLOCKED_DRAFT_KEYWORDS = (
    "جرعة", "الجرعة", "احذف", "حذف", "امسح", "امحي", "دواء", "علاج",
    "تشخيص", "وصفة", "dose", "dosage", "delete", "medicine", "prescri",
)


def draft_guardrail_reason(action_type: str, payload: dict) -> str | None:
    """يرجع سبب الرفض القطعي، أو None لو المسودة مسموحة. يُستدعى من
    `draft_action_service.py` **قبل** ما أي مسودة تصير `pending` (تظهر
    للمستخدم كبطاقة اعتماد) — رفض هنا يعني الصف يُسجَّل مباشرة بحالة
    `auto_rejected` للتوثيق بس، وما يظهر كمسودة قابلة للاعتماد إطلاقاً."""
    if action_type not in ALLOWED_DRAFT_ACTION_TYPES:
        return f"نوع إجراء غير مسموح باقتراحه تلقائياً: {action_type}"
    blob = f"{action_type} {' '.join(str(v) for v in payload.values())}".lower()
    for kw in BLOCKED_DRAFT_KEYWORDS:
        if kw.lower() in blob:
            return f"رُفضت تلقائياً — تحتوي كلمة محظورة تتعلق بجرعة دواء أو حذف سجل: \"{kw}\""
    return None


DRAFT_ACTION_TOOL_NAME = "propose_draft_action"

DRAFT_ACTION_SYSTEM_PROMPT = """أنت مساعد استخراج بيانات بس لنظام "مربي" لإدارة مزرعة. المستخدم يوصف حدث صار فعلاً بالمزرعة (بالعربي، بصيغة عامية أحياناً)، ومهمتك تحوّله لإجراء منظَّم عبر أداة propose_draft_action — لا تنفّذ أي شي بنفسك، فقط استخرج البيانات.

قواعد صارمة:
- استخدم الأداة propose_draft_action فقط لو الجملة تصف بوضوح أحد نوعين: "register_birth" (ولادة مولود جديد لأم معروفة رقمها) أو "record_weight" (تسجيل وزن رأس معروف رقمه).
- لو الجملة تخص أي شي ثاني (دواء، جرعة، حذف، بيع، تحصين...) لا تستخدم الأداة إطلاقاً — فقط اكتب رداً نصياً يوضّح إن هذا النوع من الإجراءات ما يدعم الإدخال التلقائي حالياً ويحتاج تسجيل يدوي بالشاشة المخصَّصة.
- استخرج رقم الحيوان بالضبط كما ذُكر بالجملة، بدون تخمين أو تصحيح.
- لو معلومة مطلوبة ناقصة (مثال: جنس المولود)، اتركها فاضية بالـpayload بدل ما تخمّنها.
"""


def _draft_action_tool():
    from google.genai import types
    return types.Tool(function_declarations=[types.FunctionDeclaration(
        name=DRAFT_ACTION_TOOL_NAME,
        description="اقتراح مسودة إجراء منظَّم — يحتاج اعتماد بشري قبل أي تنفيذ فعلي.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "action_type": {"type": "STRING", "enum": list(ALLOWED_DRAFT_ACTION_TYPES)},
                "target_animal_no": {"type": "STRING", "description": "رقم الحيوان المذكور"},
                "payload_json": {"type": "STRING", "description": "بقية الحقول كنص JSON صالح"},
                "summary_ar": {"type": "STRING", "description": "ملخص عربي واحد قصير للتأكيد"},
            },
            "required": ["action_type", "target_animal_no", "payload_json", "summary_ar"],
        },
    )])


def _extract_draft_action_call(response, *, fallback_summary: str) -> dict | None:
    import json
    for candidate in response.candidates or []:
        for part in (candidate.content.parts or []):
            fc = getattr(part, "function_call", None)
            if fc and fc.name == DRAFT_ACTION_TOOL_NAME:
                args = dict(fc.args)
                try:
                    payload = json.loads(args.get("payload_json") or "{}")
                except (ValueError, TypeError):
                    payload = {}
                payload["target_animal_no"] = args.get("target_animal_no")
                return {
                    "action_type": args.get("action_type"),
                    "payload": payload,
                    "summary_ar": args.get("summary_ar") or fallback_summary,
                }
    return None


def parse_draft_action(raw_text: str) -> dict | None:
    """يحلّل جملة حرة ويرجع `{"action_type", "payload", "summary_ar"}`
    لو النموذج استخدم أداة `propose_draft_action`، أو None لو رد بنص
    عادي (يعني ما تعرّف على إجراء مدعوم) أو فشل/غير مفعَّل. **فحص
    يدوي لاستدعاء الأداة، بدون تنفيذ تلقائي** — إحنا بس نقرأ الوسائط
    اللي اقترحها النموذج، صفر تنفيذ فعلي من هذا الملف."""
    if not is_gemini_configured():
        return None
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return None
    try:
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        response = client.models.generate_content(
            model=DEFAULT_GEMINI_MODEL,
            contents=raw_text,
            config=types.GenerateContentConfig(system_instruction=DRAFT_ACTION_SYSTEM_PROMPT,
                                                tools=[_draft_action_tool()]),
        )
        return _extract_draft_action_call(response, fallback_summary=raw_text)
    except Exception as e:
        try:
            from flask import current_app
            current_app.logger.warning("llm_bridge.parse_draft_action failed: %s", e)
        except Exception:
            pass
        return None


def parse_draft_action_from_audio(audio_bytes: bytes, mime_type: str) -> dict | None:
    """نفس `parse_draft_action` بالضبط، بس الإدخال مقطع صوتي — نمرّره
    مباشرة لـGemini (يدعم الصوت أصلاً كنوع محتوى) بدل تحويل نص منفصل؛
    أدق للهجة الميدانية من محركات تحويل كلام عامة (قرار معماري موثَّق
    بخطة "عقل المزرعة" المعتمدة)."""
    if not is_gemini_configured():
        return None
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return None
    try:
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        response = client.models.generate_content(
            model=DEFAULT_GEMINI_MODEL,
            contents=[types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)],
            config=types.GenerateContentConfig(system_instruction=DRAFT_ACTION_SYSTEM_PROMPT,
                                                tools=[_draft_action_tool()]),
        )
        return _extract_draft_action_call(response, fallback_summary="(من مقطع صوتي)")
    except Exception as e:
        try:
            from flask import current_app
            current_app.logger.warning("llm_bridge.parse_draft_action_from_audio failed: %s", e)
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
