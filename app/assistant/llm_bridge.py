"""
جسر الترقية المستقبلية لـ Claude API (بند 25 — معمارية هجينة).

المحرك المحلي (`nlu_service.py`) يغطي الأسئلة المتوقعة بمطابقة كلمات
مفتاحية على بيانات المزرعة الحية وقاعدة المعرفة. أي سؤال حر ما يطابق شي
محلياً يوصل هنا. لو `ANTHROPIC_API_KEY` غير موجود بـ.env، `ask()` ترجع
None فوراً بدون أي محاولة اتصال شبكة، ونلتف تلقائياً على رد "لم أفهم
سؤالك" من `nlu_service.py`.

**للترقية لاحقاً** (بدون أي تعديل على الواجهات، القوالب، أو الجداول):
1. أضف `ANTHROPIC_API_KEY=...` بملف `.env` بجذر المشروع.
2. ثبّت الحزمة: `pip install anthropic` وأضفها لـ requirements.txt.
هذا الملف هو نقطة الربط الوحيدة — كل شي ثاني بالنظام يبقى كما هو.
"""
import os

SYSTEM_PROMPT_TEMPLATE = """أنت المساعد الذكي لنظام "مربي" لإدارة مزرعة أغنام/ماعز/نعام. تخاطب المربي (صاحب المزرعة) أو أحد أفراد فريقه.

قواعد صارمة:
- جاوب بالعربي دايماً، بإيجاز ووضوح، بدون مقدمات طويلة.
- اعتمد فقط على بيانات المزرعة الحية المرفقة أدناه وعلى قاعدة المعرفة التشغيلية المرفقة — لا تخترع أرقام أو أسماء حيوانات غير موجودة بالسياق المعطى.
- المساعد قرار مو طبيب: ممنوع اقتراح جرعة دواء أو تشخيص طبي نهائي لحيوان معيّن. أي قرار علاجي نهائي يحتاج الطبيب البيطري حصراً — وجّه المستخدم له عند الحاجة.
- لو السؤال خارج نطاق إدارة المزرعة تماماً، وضّح بأدب أنك مختص بشؤون المزرعة فقط.

بيانات المزرعة الحية الآن:
{context}
"""

# بند إضافي 84، 2026-08-02 — القيمة القديمة "claude-opus-4-8" مو معرِّف
# نموذج حقيقي إطلاقاً (خطأ كتابي من بند 25، ما اكتُشف لأن ask() يبتلع
# كل الاستثناءات ويرجع None بصمت — لو حد فعّل المفتاح، كانت كل محاولة
# تفشل بصمت وترجع لنفس "لم أفهم سؤالك" بدون أي مؤشر خطأ). صار
# claude-sonnet-5 (قدرة عالية وتكلفة معقولة، الافتراضي الموصى به حالياً).
DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")


def is_configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def ask(question: str, context_text: str) -> str | None:
    """يرجع رد Claude، أو None لو المفتاح غير مُفعّل أو صار أي خطأ (نرجع
    None عمداً بدل رفع استثناء — nlu_service.py يلتف على fallback محلي)."""
    if not is_configured():
        return None
    try:
        import anthropic
    except ImportError:
        return None
    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT_TEMPLATE.format(context=context_text),
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
