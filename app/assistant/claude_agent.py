"""وكيل المزرعة المتكامل بـClaude (محادثة فورية: يقرأ، يبحث، وينفّذ).

يستبدل مسار Gemini بالأدوات متى ما كان `ANTHROPIC_API_KEY` مضبوطاً؛ لو
فشل أو غير مفعَّل يرجع `run()` بـNone فيكمل المسار المحلي القديم كما كان.

**سياسة التنفيذ (مفروضة بالخادم، مو بثقة النموذج)**:
- الافتراضي (طلب المالك: "لازم يستشيرني"): أي إجراء يغيّر بيانات لا ينفَّذ من
  تلقاء الوكيل؛ الأداة تحفظ مسودة وترجع `needs_confirmation`، والوكيل يسألك
  سؤالاً قصيراً واحداً ("أسجّلها؟")، والتنفيذ يتم فقط بأداة `confirm_action`
  وبشرط أن رسالتك الحالية تأكيد صريح ("نعم"...) ومسودتك أنت وعمرها أقل
  من 30 دقيقة.
- للتخفيف لاحقاً: متغير البيئة `AGENT_CONFIRM_TYPES` — "none" لكل شيء فوري، أو
  قائمة أنواع مفصولة بفواصل تُطلب لها الاستشارة فقط (مثل `record_sale,record_death`).
- الحواجز الصلبة دايماً بغض النظر: صلاحية كل نوع، `draft_guardrail_reason`
  (حدود المبالغ/الأسعار)، بوابة دورة الإنتاج وفترة التحريم عند البيع، منع
  القرابة الوراثية، وسجل `AssistantDraftAction` + AuditLog لكل تنفيذ.
- ممنوع دائماً: جرعات الأدوية والحذف (لا توجد أداة لها أصلاً).
"""
import inspect
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone

MAX_TURNS = 8
# مهلة صلبة: الواجهة تتوقف عن الانتظار بعد 45 ثانية وgunicorn يقتل العامل
# عند 60، فلازم الوكيل يخلص (أو يعتذر بسبب واضح) قبلها — بدل ما يعلّق
# الطلب وتطلع للمستخدم رسالة "تعذّر الاتصال" بلا أي تفسير.
CLIENT_TIMEOUT_SECONDS = 30.0
TIME_BUDGET_SECONDS = 38.0
# بادئة رسائل الأعطال — nlu_service يسجّلها answered_by="claude_error" فلا
# تدخل ذاكرة المحادثة المرسلة للنموذج.
ERROR_PREFIX = "⚠️ وكيل Claude"
MAX_OUTPUT_TOKENS = 4096
HISTORY_MESSAGES = 12
CONFIRM_WINDOW_MINUTES = 30
# كل أدوات الكتابة. الافتراضي: كلها تستشيرك أولاً (طلبك الصريح). التخفيف
# اختياري عبر AGENT_CONFIRM_TYPES فقط.
SENSITIVE_TYPES = ("record_expense", "register_birth", "record_vaccination",
                   "record_sale", "record_death", "set_purpose", "send_to_market",
                   "record_disease", "record_mating", "record_pregnancy", "confirm_pregnancy",
                   "record_abortion", "create_animal", "edit_animal", "record_stock_purchase")
ROUTINE_TYPES = ("record_weight", "assign_task", "move_animal", "add_animal_note", "add_farm_note",
                 "complete_task", "start_task", "record_milk", "request_checkup", "return_from_market")
ALL_WRITE_TYPES = SENSITIVE_TYPES + ROUTINE_TYPES


def _confirm_types() -> tuple:
    raw = (os.environ.get("AGENT_CONFIRM_TYPES") or "").strip()
    if not raw or raw.lower() == "all":
        return ALL_WRITE_TYPES
    if raw.lower() == "none":
        return ()
    return tuple(t for t in (x.strip() for x in raw.split(",")) if t in ALL_WRITE_TYPES)


def _immediate(action_type: str) -> bool:
    return action_type not in _confirm_types()


DEFAULT_MODEL = os.environ.get("ANTHROPIC_AGENT_MODEL", "claude-sonnet-5-5")

SYSTEM_PROMPT = """أنت وكيل المزرعة الذكي لنظام "مربي" لإدارة مزرعة أغنام/ماعز/نعام. تحادث المربي أو أحد أفراد فريقه محادثة فورية، وتقدر تقرأ بيانات المزرعة وتنفّذ إجراءات عبر الأدوات.

قواعد صارمة:
- {language_instruction}
- بإيجاز ووضوح، بدون مقدمات. ممنوع تنسيق ماركداون (لا نجوم، لا #). للتعداد استخدم "1." عادية.
- أي رقم أو حالة تخص المزرعة تأخذها من الأدوات فقط. ممنوع تخترع أرقاماً أو أسماء حيوانات.
- لو الأداة رجعت status "ambiguous" (نتائج متعددة) اسأل المستخدم يحدد، ممنوع تخمّن.
{policy}
- رقم الحيوان واسم الحظيرة واللقاح والسعر يجيبها المستخدم؛ لو ناقصة اسأله، ممنوع تخمّن. السعر لا تخترعه أبداً.
- create_animal (إضافة رأس جديد بالصوت) يحتاج: الرقم، الجنس، الحظيرة، اللون، والمصدر (شراء purchase / هدية gift / رصيد افتتاحي opening_balance). اسأل عن الناقص واحداً واحداً بإيجاز، والسعر لا تخترعه (يمكن تركه لو ما ذكره)، والوزن والسلالة والاسم اختيارية. المواليد لها register_birth وليس create_animal.
- edit_animal يعدّل الرقم (مثل استبدال TEMP-... بالرقم الدائم) أو الاسم أو اللون أو السلالة؛ الغرض والحظيرة والجنس لها أدواتها. record_stock_purchase لشراء علف (feed) أو دواء (pharmacy) أو معدات (equipment) للمخزون باسم الصنف والكمية وسعر الوحدة (السعر مطلوب للعلف والمعدات، والسعر لا تخترعه).
- request_checkup يحتاج اسم عضو الفريق من المستخدم (مثل assign_task). record_milk يحتاج الحلبة (صباح/مساء) والكمية باللتر. record_disease لتسجيل اسم المرض فقط بدون أي علاج أو جرعة.
- record_mating: رقم الأنثى + رقم الفحل (أو وصفه لو خارجي). التقريع بين أقارب وراثياً يُرفض ويُوجَّه المستخدم لشاشة التقريع. record_pregnancy: مؤكَّد (confirmed=true) فقط لو المستخدم قال سونار/مؤكد، وإلا غير مؤكد. confirm_pregnancy يؤكد آخر حمل غير مؤكد للأنثى.
- record_abortion يسجّل إجهاض آخر حمل مفتوح للأنثى ويشغّل بروتوكول العزل (نقلها لحظيرة العزل ومهام عيّنات ومراقبة). اذكر في ردك أنه شغّل بروتوكول العزل.
- لأسئلة "كم رأس بحظيرة كذا" استخدم barn_summary، ولإنتاج الحليب milk_summary.
- complete_task تنهي مهمة مفتوحة مكلَّف بها المستخدم نفسه بعنوانها (من my_tasks_summary).
- assign_task تحتاج اسم عضو الفريق المكلَّف من المستخدم؛ لو ما ذكره اسأله، ممنوع تختاره بنفسك.
- لو أرفق المستخدم صورة فاتورة: اقرأها (المورّد، التاريخ، الإجمالي النهائي شامل الضريبة، الفئة) ثم استدعِ record_expense. لو الإجمالي غير واضح اسأله بدل التخمين.
- أداة web_search للمعلومات العامة الخارجية فقط (علف، ممارسات تربية، أسعار سوق). ابدأ أي جواب منها بـ"حسب مصادر خارجية:" واذكر المصادر باختصار، ووضّح إنها معلومة عامة مو قراراً على قطيعه. لا تستخدمها لبيانات مزرعته.
- ممنوع تقترح جرعة دواء أو تشخيصاً نهائياً أو حذف أي سجل؛ وجّه المستخدم للطبيب أو للشاشة المخصَّصة.
- لو السؤال خارج نطاق المزرعة تماماً، اعتذر بأدب وإنك مختص بالمزرعة.

اليوم: {today}
"""

VOICE_ADDENDUM = """
وضع الصوت مفعَّل: المستخدم يكلّمك بالصوت وردّك سيُقرأ بصوت عالٍ. اجعل الرد جملتين أو ثلاثاً كحدّ أقصى، بلا جداول ولا قوائم طويلة ولا رموز أو إيموجي، والأرقام تُقال كلاماً طبيعياً. نفّذ الطلب مباشرة ثم قل "تم" بجملة قصيرة، ولا تسأل إلا لو معلومة ناقصة أو غامضة؛ ولو الأداة طلبت تأكيداً (needs_confirmation) اسأل سؤالاً قصيراً واحداً فقط ("أسجّلها؟")."""

_LANGUAGE_INSTRUCTIONS = {
    "ar": "جاوب بالعربي دايماً.",
    "en": "Always answer in English.",
    "am": "ሁልጊዜ በአማርኛ መልስ ስጥ።",
    "hi": "हमेशा हिंदी में उत्तर दें।",
}

_AFFIRMATIVE = ("نعم", "ايوه", "أيوه", "ايوا", "أيوا", "ايه", "أكد", "اكد", "تأكيد", "تاكيد", "اعتمد",
                "سجل", "سجّل", "سجلها", "سجّلها", "تمام", "موافق", "yes", "ok", "okay", "y", "👍", "✅")
_NEGATIVE = ("لا ", "لأ", "ما ", "الغ", "الغي", "no", "cancel", "إلغاء", "الغاء", "خلاص", "بلاش", "لا")


def is_configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _client():
    import anthropic
    return anthropic.Anthropic(timeout=CLIENT_TIMEOUT_SECONDS, max_retries=1)


def _describe_error(e: Exception) -> str:
    """سبب عربي مقروء لعطل نداء Claude — بلا أسرار (رسالة الخدمة فقط)."""
    try:
        import anthropic
    except ImportError:
        return "حزمة anthropic غير مثبّتة على الخادم."
    detail = ""
    try:
        body = getattr(e, "body", None) or {}
        detail = (body.get("error", {}).get("message") if isinstance(body, dict) else "") or ""
    except Exception:
        detail = ""
    detail = (detail or str(e) or "").strip().replace("\n", " ")[:180]
    if isinstance(e, anthropic.AuthenticationError):
        return "مفتاح ANTHROPIC_API_KEY غير صالح أو منتهي — راجع المتغير في Render."
    if isinstance(e, anthropic.PermissionDeniedError):
        return f"المفتاح ما عنده صلاحية لهذا النموذج أو الميزة ({detail})."
    if isinstance(e, anthropic.NotFoundError):
        return f"النموذج غير موجود — راجع ANTHROPIC_AGENT_MODEL ({detail})."
    if isinstance(e, anthropic.RateLimitError):
        return "تجاوز حد الاستخدام أو الرصيد — جرّب بعد لحظات أو راجع الرصيد في Anthropic."
    if isinstance(e, anthropic.APITimeoutError):
        return "انتهت مهلة الرد من خدمة Claude — جرّب مرة ثانية."
    if isinstance(e, anthropic.APIConnectionError):
        return "تعذّر الاتصال بخدمة Claude من الخادم."
    if isinstance(e, anthropic.BadRequestError):
        return f"الطلب رُفض من الخدمة: {detail}"
    if isinstance(e, anthropic.APIStatusError):
        return f"خطأ من خدمة Claude ({getattr(e, 'status_code', '?')}): {detail}"
    return f"خطأ غير متوقع ({type(e).__name__}): {detail}"


def _error_text(reason: str) -> str:
    return f"{ERROR_PREFIX} تعذّر عليه الرد الآن: {reason}"


def is_affirmative(text: str) -> bool:
    """تأكيد صريح قصير فقط. أي نفي أو جملة طويلة تُعتبر مو تأكيداً —
    ضمان خادمي مستقل عن فهم النموذج للمحادثة."""
    t = re.sub(r"[\s\.\!\،,؟?]+", " ", (text or "").strip().lower()).strip()
    if not t or len(t) > 30:
        return False
    padded = f" {t} "
    if any(f" {n.strip()} " in padded for n in _NEGATIVE if n.strip()):
        return False
    return any(t == a or t.startswith(a + " ") or f" {a} " in padded for a in _AFFIRMATIVE)


# ---------------------------------------------------------------- أدوات القراءة

_PY_TO_JSON = {str: "string", int: "integer", float: "number", bool: "boolean"}


def _read_tool_defs(user) -> tuple[list[dict], dict]:
    """أدوات القراءة الحالية (agent_tools) بصيغة Anthropic، مفلترة بصلاحيات
    المستخدم — بدون web_research (Claude عنده بحث مدمج)."""
    from app.assistant import agent_tools
    defs, registry = [], {}
    for fn in agent_tools.build_tools_for_user(user):
        if fn.__name__ == "web_research":
            continue
        props, required = {}, []
        for name, param in inspect.signature(fn).parameters.items():
            ann = param.annotation
            base = ann
            if hasattr(ann, "__args__"):
                non_none = [a for a in ann.__args__ if a is not type(None)]
                base = non_none[0] if non_none else str
            props[name] = {"type": _PY_TO_JSON.get(base, "string")}
            if param.default is inspect.Parameter.empty:
                required.append(name)
        defs.append({
            "name": fn.__name__,
            "description": (inspect.getdoc(fn) or fn.__name__)[:900],
            "input_schema": {"type": "object", "properties": props, "required": required},
        })
        registry[fn.__name__] = fn
    return defs, registry


# --------------------------------------------------------------- أدوات التنفيذ

_WRITE_TOOL_DEFS = [
    {"name": "record_weight",
     "description": "تسجيل وزن رأس (كجم). ينفَّذ فوراً.",
     "input_schema": {"type": "object", "properties": {
         "animal_no": {"type": "string", "description": "رقم الحيوان"},
         "weight": {"type": "number", "description": "الوزن بالكيلو"}},
         "required": ["animal_no", "weight"]}},
    {"name": "assign_task",
     "description": "توزيع مهمة على عضو فريق. اسم المكلَّف لازم يجي من المستخدم. ينفَّذ فوراً.",
     "input_schema": {"type": "object", "properties": {
         "task_title": {"type": "string"},
         "assignee_name": {"type": "string", "description": "اسم عضو الفريق كما ذكره المستخدم"},
         "animal_no": {"type": "string", "description": "اختياري"},
         "due_date": {"type": "string", "description": "اختياري YYYY-MM-DD"}},
         "required": ["task_title", "assignee_name"]}},
    {"name": "register_birth",
     "description": "تسجيل ولادة (ينشئ مولوداً جديداً).",
     "input_schema": {"type": "object", "properties": {
         "mother_no": {"type": "string"},
         "gender": {"type": "string", "enum": ["ذكر", "أنثى"]},
         "weight": {"type": "number", "description": "اختياري"}},
         "required": ["mother_no", "gender"]}},
    {"name": "record_expense",
     "description": "تسجيل فاتورة مورّد كمصروف.",
     "input_schema": {"type": "object", "properties": {
         "supplier": {"type": "string"},
         "total_amount": {"type": "number", "description": "الإجمالي النهائي شامل الضريبة"},
         "invoice_date": {"type": "string", "description": "YYYY-MM-DD أو فاضي لليوم"},
         "category": {"type": "string",
                      "enum": ["أعلاف", "أدوية", "معدات", "صيانة معدات", "فاتورة كهرباء", "فاتورة ماء", "بدون تصنيف"]},
         "description": {"type": "string"}},
         "required": ["total_amount", "category"]}},
    {"name": "move_animal",
     "description": "نقل حيوان لحظيرة (باسمها). ينفَّذ فوراً.",
     "input_schema": {"type": "object", "properties": {
         "animal_no": {"type": "string"}, "barn_name": {"type": "string"}},
         "required": ["animal_no", "barn_name"]}},
    {"name": "add_animal_note",
     "description": "إضافة ملاحظة نصية على سجل حيوان. ينفَّذ فوراً.",
     "input_schema": {"type": "object", "properties": {
         "animal_no": {"type": "string"}, "note": {"type": "string"}},
         "required": ["animal_no", "note"]}},
    {"name": "add_farm_note",
     "description": "حفظ ملاحظة عامة بدفتر المزرعة. ينفَّذ فوراً.",
     "input_schema": {"type": "object", "properties": {
         "body": {"type": "string"}, "title": {"type": "string", "description": "اختياري"}},
         "required": ["body"]}},
    {"name": "complete_task",
     "description": "إنهاء مهمة مفتوحة للمستخدم بعنوانها. ينفَّذ فوراً.",
     "input_schema": {"type": "object", "properties": {
         "task_title": {"type": "string"}, "note": {"type": "string", "description": "اختياري"}},
         "required": ["task_title"]}},
    {"name": "record_vaccination",
     "description": "تسجيل تحصين لحيوان بتاريخ اليوم.",
     "input_schema": {"type": "object", "properties": {
         "animal_no": {"type": "string"}, "vaccine_name": {"type": "string"},
         "next_due_date": {"type": "string", "description": "اختياري YYYY-MM-DD"}},
         "required": ["animal_no", "vaccine_name"]}},
    {"name": "record_sale",
     "description": "تسجيل بيع رأس بسعر يحدده المستخدم.",
     "input_schema": {"type": "object", "properties": {
         "animal_no": {"type": "string"}, "price": {"type": "number", "description": "سعر البيع بالريال"},
         "sale_date": {"type": "string", "description": "اختياري YYYY-MM-DD"}},
         "required": ["animal_no", "price"]}},
    {"name": "record_death",
     "description": "تسجيل نفوق رأس.",
     "input_schema": {"type": "object", "properties": {
         "animal_no": {"type": "string"}, "reason": {"type": "string", "description": "اختياري"}},
         "required": ["animal_no"]}},
    {"name": "start_task",
     "description": "بدء مهمة مفتوحة للمستخدم بعنوانها. ينفَّذ فوراً.",
     "input_schema": {"type": "object", "properties": {"task_title": {"type": "string"}},
                      "required": ["task_title"]}},
    {"name": "record_milk",
     "description": "تسجيل حلبة حليب لحيوان بتاريخ اليوم. ينفَّذ فوراً.",
     "input_schema": {"type": "object", "properties": {
         "animal_no": {"type": "string"}, "session": {"type": "string", "enum": ["صباح", "مساء"]},
         "liters": {"type": "number", "description": "الكمية باللتر"}},
         "required": ["animal_no", "session", "liters"]}},
    {"name": "request_checkup",
     "description": "طلب فحص لحيوان من عضو فريق (دكتور مثلاً). اسم المكلَّف لازم يجي من المستخدم. ينفَّذ فوراً.",
     "input_schema": {"type": "object", "properties": {
         "animal_no": {"type": "string"},
         "items": {"type": "array", "items": {"type": "string"}, "description": "بنود الفحص المطلوبة"},
         "assignee_name": {"type": "string"},
         "due_date": {"type": "string", "description": "اختياري YYYY-MM-DD"}},
         "required": ["animal_no", "items", "assignee_name"]}},
    {"name": "set_purpose",
     "description": "تحديد غرض رأس: تربية أو تسمين أو بيع.",
     "input_schema": {"type": "object", "properties": {
         "animal_no": {"type": "string"}, "purpose": {"type": "string", "enum": ["تربية", "تسمين", "بيع"]}},
         "required": ["animal_no", "purpose"]}},
    {"name": "send_to_market",
     "description": "تسجيل إطلاع رأس للسوق (يمر ببوابة البيع).",
     "input_schema": {"type": "object", "properties": {
         "animal_no": {"type": "string"}, "note": {"type": "string", "description": "اختياري"}},
         "required": ["animal_no"]}},
    {"name": "return_from_market",
     "description": "تسجيل رجوع رأس من السوق بدون بيع. ينفَّذ فوراً.",
     "input_schema": {"type": "object", "properties": {
         "animal_no": {"type": "string"}, "note": {"type": "string", "description": "اختياري"}},
         "required": ["animal_no"]}},
    {"name": "record_disease",
     "description": "تسجيل مرض لحيوان (اسم المرض فقط، بدون أدوية أو جرعات).",
     "input_schema": {"type": "object", "properties": {
         "animal_no": {"type": "string"}, "disease_name": {"type": "string"},
         "severity": {"type": "string", "enum": ["light", "medium", "severe"],
                      "description": "بسيطة/متوسطة/شديدة"}},
         "required": ["animal_no", "disease_name"]}},
    {"name": "record_mating",
     "description": "تسجيل تقريع/تلقيح لأنثى بتاريخ اليوم (أو تاريخ يحدده المستخدم).",
     "input_schema": {"type": "object", "properties": {
         "female_no": {"type": "string"}, "male_no": {"type": "string", "description": "رقم الفحل المسجَّل"},
         "male_note": {"type": "string", "description": "وصف الفحل لو خارجي/غير مسجَّل"},
         "mating_date": {"type": "string", "description": "اختياري YYYY-MM-DD"},
         "notes": {"type": "string", "description": "اختياري"}},
         "required": ["female_no"]}},
    {"name": "record_pregnancy",
     "description": "تسجيل تشخيص حمل لأنثى.",
     "input_schema": {"type": "object", "properties": {
         "female_no": {"type": "string"},
         "confirmed": {"type": "boolean", "description": "true فقط لو الحمل مؤكَّد (سونار/فحص)"},
         "embryo_count": {"type": "integer", "description": "اختياري"},
         "sonar_date": {"type": "string", "description": "اختياري YYYY-MM-DD"},
         "pregnancy_date": {"type": "string", "description": "اختياري YYYY-MM-DD، الافتراضي اليوم"},
         "notes": {"type": "string", "description": "اختياري"}},
         "required": ["female_no"]}},
    {"name": "confirm_pregnancy",
     "description": "تأكيد آخر حمل غير مؤكَّد مسجَّل لأنثى (يدخلها بعدّاد الحوامل).",
     "input_schema": {"type": "object", "properties": {"female_no": {"type": "string"}},
                      "required": ["female_no"]}},
    {"name": "record_abortion",
     "description": "تسجيل إجهاض لأنثى (آخر حمل مفتوح لها) وتشغيل بروتوكول العزل الطبي.",
     "input_schema": {"type": "object", "properties": {
         "female_no": {"type": "string"}, "notes": {"type": "string", "description": "اختياري"}},
         "required": ["female_no"]}},
    {"name": "create_animal",
     "description": "إضافة رأس جديد للمزرعة (شراء أو هدية أو رصيد افتتاحي). الشراء بسعر يسجّل مصروف شراء تلقائياً.",
     "input_schema": {"type": "object", "properties": {
         "animal_no": {"type": "string", "description": "رقم/رقعة الحيوان الجديد"},
         "gender": {"type": "string", "enum": ["ذكر", "أنثى"]},
         "source": {"type": "string", "enum": ["purchase", "gift", "opening_balance"]},
         "barn_name": {"type": "string"}, "color": {"type": "string"},
         "weight": {"type": "number", "description": "اختياري كجم"},
         "price": {"type": "number", "description": "سعر الشراء، اختياري"},
         "breed": {"type": "string", "description": "اختياري"}, "name": {"type": "string", "description": "اختياري"},
         "purpose": {"type": "string", "enum": ["تربية", "تسمين", "بيع"], "description": "اختياري"},
         "species": {"type": "string", "description": "اختياري، الافتراضي sheep_goat"},
         "mother_no": {"type": "string", "description": "اختياري"}, "father_no": {"type": "string", "description": "اختياري"},
         "purchase_date": {"type": "string", "description": "اختياري YYYY-MM-DD"},
         "is_pregnant": {"type": "boolean", "description": "أنثى مشتراة حامل"}},
         "required": ["animal_no", "gender", "source", "barn_name", "color"]}},
    {"name": "edit_animal",
     "description": "تعديل رقم/اسم/لون/سلالة رأس موجود (أهم استخدام: استبدال الرقم المؤقت TEMP-... بالدائم).",
     "input_schema": {"type": "object", "properties": {
         "animal_no": {"type": "string", "description": "الرقم الحالي للرأس"},
         "new_animal_no": {"type": "string", "description": "الرقم الجديد"},
         "name": {"type": "string"}, "color": {"type": "string"}, "breed": {"type": "string"}},
         "required": ["animal_no"]}},
    {"name": "record_stock_purchase",
     "description": "تسجيل شراء علف أو دواء أو معدات للمخزون: يزيد الكمية ويسجّل العملية المالية بسعر الوحدة.",
     "input_schema": {"type": "object", "properties": {
         "kind": {"type": "string", "enum": ["feed", "pharmacy", "equipment"]},
         "item_name": {"type": "string", "description": "اسم الصنف كما هو بالمخزون"},
         "quantity": {"type": "number"},
         "unit_price": {"type": "number", "description": "سعر الوحدة بالريال، مطلوب للعلف والمعدات"},
         "expiry_date": {"type": "string", "description": "اختياري للدواء YYYY-MM-DD"},
         "note": {"type": "string", "description": "اختياري"}},
         "required": ["kind", "item_name", "quantity"]}},
    {"name": "confirm_action",
     "description": "تنفيذ إجراء معلَّق بعد تأكيد المستخدم الصريح بآخر رسالة له.",
     "input_schema": {"type": "object", "properties": {"draft_id": {"type": "integer"}},
                      "required": ["draft_id"]}},
]


def _write_tool_allowed(user, tool_name: str) -> bool:
    from app.assistant import draft_action_service
    if tool_name == "confirm_action":
        return user.has_permission("assistant.draft_actions.confirm")
    perm = draft_action_service.ALLOWED_ACTION_TYPES[tool_name]["required_permission"]
    return user.has_permission(perm)


class _Ctx:
    def __init__(self, user, message_text, image_url=None):
        self.user = user
        self.message_text = message_text
        self.image_url = image_url


def _now():
    return datetime.now(timezone.utc)


def _record_and_run(ctx: _Ctx, action_type: str, payload: dict, summary: str, *, execute_now: bool) -> dict:
    from app.extensions import db
    from app.models import AssistantDraftAction
    from app.assistant import draft_action_service, llm_bridge

    action_def = draft_action_service.ALLOWED_ACTION_TYPES[action_type]
    if not ctx.user.has_permission(action_def["required_permission"]):
        return {"status": "forbidden", "message": f"ما عندك صلاحية: {action_def['required_permission']}"}
    reason = llm_bridge.draft_guardrail_reason(action_type, payload)
    if reason:
        return {"status": "rejected", "message": reason}

    draft = AssistantDraftAction(
        raw_text=ctx.message_text or "(محادثة)", input_source="chat",
        parsed_action_type=action_type,
        parsed_payload_json=AssistantDraftAction.encode_payload(payload),
        summary_ar=summary, created_by_id=ctx.user.id, status="pending",
    )
    db.session.add(draft)
    db.session.commit()
    if not execute_now:
        return {"status": "needs_confirmation", "draft_id": draft.id, "summary": summary}
    return _execute(ctx, draft)


def _execute(ctx: _Ctx, draft, assignee_id=None) -> dict:
    from app.extensions import db
    from app.assistant import draft_action_service
    try:
        draft_action_service.confirm_draft(draft, actor=ctx.user, assignee_id=assignee_id)
    except Exception as e:  # فشل التنفيذ يرجع للنموذج كنص ليشرحه، مو انهيار المحادثة
        db.session.rollback()
        return {"status": "error", "message": str(e)}
    return {"status": "done", "summary": draft.summary_ar}


def _tool_record_weight(ctx, args):
    return _record_and_run(ctx, "record_weight",
                           {"target_animal_no": str(args.get("animal_no", "")).strip(), "weight": args.get("weight")},
                           f"تسجيل وزن {args.get('weight')} كجم للرأس {args.get('animal_no')}", execute_now=_immediate("record_weight"))


def _find_assignee(name):
    """يرجع (المستخدم, None) أو (None, ردّ_خطأ) — اسم الدكتور/العامل يجي
    من المستخدم حرفياً، ولو غامض نرجّع القائمة بدل التخمين."""
    from app.models import User
    name = str(name or "").strip()
    matches = [u for u in User.query.filter_by(is_active_account=True).all() if name and name in (u.name or "")]
    if not matches:
        return None, {"status": "error", "message": f'ما لقيت عضو فريق باسم "{name}".'}
    if len(matches) > 1:
        return None, {"status": "ambiguous", "candidates": [u.name for u in matches[:6]]}
    return matches[0], None


def _tool_assign_task(ctx, args):
    assignee, err = _find_assignee(args.get("assignee_name"))
    if err:
        return err
    matches = [assignee]
    payload = {"task_title": args.get("task_title"), "due_date": args.get("due_date") or None,
               "target_animal_no": (args.get("animal_no") or None), "assignee_id": matches[0].id}
    draft_result = _record_and_run(ctx, "assign_task", payload,
                                   f"توزيع مهمة \"{args.get('task_title')}\" على {matches[0].name}",
                                   execute_now=False)
    if draft_result.get("status") != "needs_confirmation" or not _immediate("assign_task"):
        return draft_result
    from app.models import AssistantDraftAction
    return _execute(ctx, AssistantDraftAction.query.get(draft_result["draft_id"]), assignee_id=matches[0].id)


def _tool_register_birth(ctx, args):
    payload = {"target_animal_no": str(args.get("mother_no", "")).strip(),
               "newborn_gender": args.get("gender"), "newborn_weight": args.get("weight")}
    return _record_and_run(ctx, "register_birth", payload,
                           f"تسجيل ولادة للأم {args.get('mother_no')} — {args.get('gender')}", execute_now=_immediate("register_birth"))


def _tool_record_expense(ctx, args):
    payload = {"supplier": args.get("supplier"), "invoice_date": args.get("invoice_date") or None,
               "total_amount": args.get("total_amount"), "category": args.get("category") or "بدون تصنيف",
               "description": args.get("description")}
    if ctx.image_url:
        payload["invoice_file_url"] = ctx.image_url
    return _record_and_run(ctx, "record_expense", payload,
                           f"فاتورة {args.get('supplier') or '-'} بمبلغ {args.get('total_amount')} ({payload['category']})",
                           execute_now=_immediate("record_expense"))


def _tool_move_animal(ctx, args):
    return _record_and_run(
        ctx, "move_animal",
        {"target_animal_no": str(args.get("animal_no", "")).strip(), "barn_name": args.get("barn_name")},
        f"نقل الرأس {args.get('animal_no')} إلى حظيرة {args.get('barn_name')}", execute_now=_immediate("move_animal"))


def _tool_add_animal_note(ctx, args):
    return _record_and_run(
        ctx, "add_animal_note",
        {"target_animal_no": str(args.get("animal_no", "")).strip(), "note": args.get("note")},
        f"ملاحظة على الرأس {args.get('animal_no')}", execute_now=_immediate("add_animal_note"))


def _tool_add_farm_note(ctx, args):
    return _record_and_run(ctx, "add_farm_note", {"body": args.get("body"), "title": args.get("title")},
                           "ملاحظة بدفتر المزرعة", execute_now=_immediate("add_farm_note"))


def _tool_complete_task(ctx, args):
    return _record_and_run(ctx, "complete_task",
                           {"task_title": args.get("task_title"), "note": args.get("note")},
                           f"إنهاء مهمة: {args.get('task_title')}", execute_now=_immediate("complete_task"))


def _tool_record_vaccination(ctx, args):
    return _record_and_run(
        ctx, "record_vaccination",
        {"target_animal_no": str(args.get("animal_no", "")).strip(), "vaccine_name": args.get("vaccine_name"),
         "next_due_date": args.get("next_due_date") or None},
        f"تحصين {args.get('vaccine_name')} للرأس {args.get('animal_no')}", execute_now=_immediate("record_vaccination"))


def _tool_record_sale(ctx, args):
    return _record_and_run(
        ctx, "record_sale",
        {"target_animal_no": str(args.get("animal_no", "")).strip(), "price": args.get("price"),
         "sale_date": args.get("sale_date") or None},
        f"بيع الرأس {args.get('animal_no')} بسعر {args.get('price')}", execute_now=_immediate("record_sale"))


def _tool_record_death(ctx, args):
    return _record_and_run(
        ctx, "record_death",
        {"target_animal_no": str(args.get("animal_no", "")).strip(), "reason": args.get("reason") or None},
        f"تسجيل نفوق الرأس {args.get('animal_no')}", execute_now=_immediate("record_death"))


def _tool_start_task(ctx, args):
    return _record_and_run(ctx, "start_task", {"task_title": args.get("task_title")},
                           f"بدء مهمة: {args.get('task_title')}", execute_now=_immediate("start_task"))


def _tool_record_milk(ctx, args):
    return _record_and_run(
        ctx, "record_milk",
        {"target_animal_no": str(args.get("animal_no", "")).strip(), "session": args.get("session"),
         "liters": args.get("liters")},
        f"حليب {args.get('liters')} لتر ({args.get('session')}) للرأس {args.get('animal_no')}", execute_now=_immediate("record_milk"))


def _tool_request_checkup(ctx, args):
    assignee, err = _find_assignee(args.get("assignee_name"))
    if err:
        return err
    items = args.get("items") or []
    draft_result = _record_and_run(
        ctx, "request_checkup",
        {"target_animal_no": str(args.get("animal_no", "")).strip(), "items": items,
         "due_date": args.get("due_date") or None, "assignee_id": assignee.id},
        f"طلب فحص ({'، '.join(map(str, items))}) للرأس {args.get('animal_no')} من {assignee.name}",
        execute_now=False)
    if draft_result.get("status") != "needs_confirmation" or not _immediate("request_checkup"):
        return draft_result
    from app.models import AssistantDraftAction
    return _execute(ctx, AssistantDraftAction.query.get(draft_result["draft_id"]), assignee_id=assignee.id)


def _tool_set_purpose(ctx, args):
    return _record_and_run(
        ctx, "set_purpose",
        {"target_animal_no": str(args.get("animal_no", "")).strip(), "purpose": args.get("purpose")},
        f"تحديد غرض الرأس {args.get('animal_no')}: {args.get('purpose')}", execute_now=_immediate("set_purpose"))


def _tool_send_to_market(ctx, args):
    return _record_and_run(
        ctx, "send_to_market",
        {"target_animal_no": str(args.get("animal_no", "")).strip(), "note": args.get("note") or None},
        f"إطلاع الرأس {args.get('animal_no')} للسوق", execute_now=_immediate("send_to_market"))


def _tool_return_from_market(ctx, args):
    return _record_and_run(
        ctx, "return_from_market",
        {"target_animal_no": str(args.get("animal_no", "")).strip(), "note": args.get("note") or None},
        f"رجوع الرأس {args.get('animal_no')} من السوق", execute_now=_immediate("return_from_market"))


def _tool_record_disease(ctx, args):
    return _record_and_run(
        ctx, "record_disease",
        {"target_animal_no": str(args.get("animal_no", "")).strip(), "disease_name": args.get("disease_name"),
         "severity": args.get("severity") or "medium"},
        f"تسجيل مرض {args.get('disease_name')} للرأس {args.get('animal_no')}", execute_now=_immediate("record_disease"))


def _tool_record_mating(ctx, args):
    male = str(args.get("male_no") or "").strip() or None
    return _record_and_run(
        ctx, "record_mating",
        {"target_animal_no": str(args.get("female_no", "")).strip(), "male_no": male,
         "male_note": args.get("male_note") or None, "mating_date": args.get("mating_date") or None,
         "notes": args.get("notes") or None},
        f"تقريع الأنثى {args.get('female_no')} مع " + (f"الفحل {male}" if male else f"فحل خارجي ({args.get('male_note') or '-'})"),
        execute_now=_immediate("record_mating"))


def _tool_record_pregnancy(ctx, args):
    state = "مؤكَّد" if args.get("confirmed") else "غير مؤكَّد"
    return _record_and_run(
        ctx, "record_pregnancy",
        {"target_animal_no": str(args.get("female_no", "")).strip(), "confirmed": bool(args.get("confirmed")),
         "embryo_count": args.get("embryo_count"), "sonar_date": args.get("sonar_date") or None,
         "pregnancy_date": args.get("pregnancy_date") or None, "notes": args.get("notes") or None},
        f"تشخيص حمل {state} للأنثى {args.get('female_no')}", execute_now=_immediate("record_pregnancy"))


def _tool_confirm_pregnancy(ctx, args):
    return _record_and_run(
        ctx, "confirm_pregnancy", {"target_animal_no": str(args.get("female_no", "")).strip()},
        f"تأكيد حمل الأنثى {args.get('female_no')}", execute_now=_immediate("confirm_pregnancy"))


def _tool_record_abortion(ctx, args):
    return _record_and_run(
        ctx, "record_abortion",
        {"target_animal_no": str(args.get("female_no", "")).strip(), "notes": args.get("notes") or None},
        f"تسجيل إجهاض للأنثى {args.get('female_no')} (يشغّل بروتوكول العزل)", execute_now=_immediate("record_abortion"))


def _tool_create_animal(ctx, args):
    payload = {
        "new_animal_no": str(args.get("animal_no", "")).strip(), "gender": args.get("gender"),
        "source": args.get("source"), "barn_name": args.get("barn_name"), "color": args.get("color"),
        "weight": args.get("weight"), "price": args.get("price"), "breed": args.get("breed") or None,
        "name": args.get("name") or None, "purpose": args.get("purpose") or None,
        "species": args.get("species") or None, "mother_no": args.get("mother_no") or None,
        "father_no": args.get("father_no") or None, "purchase_date": args.get("purchase_date") or None,
        "is_pregnant": bool(args.get("is_pregnant")),
    }
    extra = f" بسعر {args.get('price')}" if args.get("price") not in (None, "") else ""
    return _record_and_run(
        ctx, "create_animal", payload,
        f"إضافة رأس جديد {args.get('animal_no')} ({args.get('gender')}، {args.get('color')}) لحظيرة {args.get('barn_name')}{extra}",
        execute_now=_immediate("create_animal"))


def _tool_edit_animal(ctx, args):
    changes = [k for k in ("new_animal_no", "name", "color", "breed") if args.get(k)]
    return _record_and_run(
        ctx, "edit_animal",
        {"target_animal_no": str(args.get("animal_no", "")).strip(), "new_animal_no": args.get("new_animal_no") or None,
         "name": args.get("name") or None, "color": args.get("color") or None, "breed": args.get("breed") or None},
        f"تعديل بيانات الرأس {args.get('animal_no')}: " + "، ".join(
            f"{k}={args.get(k)}" for k in changes), execute_now=_immediate("edit_animal"))


def _tool_record_stock_purchase(ctx, args):
    from app.assistant import draft_action_service
    kind = str(args.get("kind") or "").strip()
    perm = draft_action_service._STOCK_KIND_PERMISSION.get(kind)
    if perm and not ctx.user.has_permission(perm):
        return {"status": "forbidden", "message": f"ما عندك صلاحية: {perm}"}
    price = args.get("unit_price")
    if price not in (None, "") and not ctx.user.has_permission("finance.full.manage"):
        return {"status": "forbidden", "message": "ما عندك صلاحية: finance.full.manage"}
    labels = {"feed": "علف", "pharmacy": "دواء", "equipment": "معدات"}
    price_txt = f" بسعر {price} للوحدة" if price not in (None, "") else ""
    return _record_and_run(
        ctx, "record_stock_purchase",
        {"kind": kind, "item_name": args.get("item_name"), "quantity": args.get("quantity"),
         "unit_price": price if price not in ("",) else None, "expiry_date": args.get("expiry_date") or None,
         "note": args.get("note") or None},
        f"شراء {labels.get(kind, kind)}: {args.get('item_name')} × {args.get('quantity')}{price_txt}",
        execute_now=_immediate("record_stock_purchase"))


def _tool_confirm_action(ctx, args):
    from app.models import AssistantDraftAction
    if not is_affirmative(ctx.message_text):
        return {"status": "refused", "message": "رسالة المستخدم الحالية مو تأكيداً صريحاً — اسأله وانتظر رده."}
    draft = AssistantDraftAction.query.get(args.get("draft_id"))
    if not draft or draft.created_by_id != ctx.user.id or draft.status != "pending":
        return {"status": "error", "message": "ما فيه إجراء معلَّق بهذا الرقم."}
    created = draft.created_at
    if created is not None:
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if _now() - created > timedelta(minutes=CONFIRM_WINDOW_MINUTES):
            return {"status": "error", "message": "انتهت مهلة التأكيد (30 دقيقة) — اطلب الإجراء من جديد."}
    if draft.parsed_action_type not in _confirm_types():
        return {"status": "error", "message": "هذا الإجراء ما يحتاج تأكيداً."}
    return _execute(ctx, draft, assignee_id=draft.get_payload().get("assignee_id"))


_WRITE_TOOLS = {
    "record_weight": _tool_record_weight, "assign_task": _tool_assign_task,
    "register_birth": _tool_register_birth, "record_expense": _tool_record_expense,
    "move_animal": _tool_move_animal, "add_animal_note": _tool_add_animal_note,
    "add_farm_note": _tool_add_farm_note, "complete_task": _tool_complete_task,
    "record_vaccination": _tool_record_vaccination, "record_sale": _tool_record_sale,
    "record_death": _tool_record_death,
    "start_task": _tool_start_task, "record_milk": _tool_record_milk,
    "request_checkup": _tool_request_checkup, "set_purpose": _tool_set_purpose,
    "send_to_market": _tool_send_to_market, "return_from_market": _tool_return_from_market,
    "record_disease": _tool_record_disease,
    "record_mating": _tool_record_mating, "record_pregnancy": _tool_record_pregnancy,
    "confirm_pregnancy": _tool_confirm_pregnancy, "record_abortion": _tool_record_abortion,
    "create_animal": _tool_create_animal, "edit_animal": _tool_edit_animal,
    "record_stock_purchase": _tool_record_stock_purchase,
    "confirm_action": _tool_confirm_action,
}


# --------------------------------------------------------------------- الحلقة

_IMMEDIATE_POLICY = (
    "- كل إجراء ينفَّذ فوراً بمجرد استدعاء الأداة: بعدها قل \"تم\" مع التفاصيل بجملة قصيرة "
    "(للبيع والنفوق والإجهاض كرّر الرقم والسعر في ردك ليسهل تصحيحه)."
)


def _policy_text() -> str:
    confirm = _confirm_types()
    if not confirm:
        return _IMMEDIATE_POLICY
    if set(confirm) >= set(ALL_WRITE_TYPES):
        scope = "كل أدوات الكتابة (أي إجراء يغيّر بيانات)"
    else:
        scope = "هذي الأدوات: " + "، ".join(confirm) + " (والباقي ينفَّذ فوراً وقل \"تم\")"
    return (
        "- " + scope + " ترجع needs_confirmation ولا تنفَّذ من تلقاء نفسها: المالك طلب صراحة أنك تستشيره قبل أي "
        "تنفيذ. اعرض التفاصيل بسطر واحد (للبيع اذكر الرقم والسعر) واسأل \"أسجّلها؟\" وانتظر. "
        "لما يرد المستخدم بتأكيد صريح (نعم/أكّد) استدعِ confirm_action بنفس draft_id، وبعدها قل \"تم\" "
        "مع التفاصيل. لو رفض أو غيّر شيئاً (رقم/سعر) لا تستدعها؛ استدعِ الأداة من جديد بالقيم المعدَّلة.\n"
        "- معلومة ناقصة أو غامضة (رقم حيوان، سعر، حظيرة، اسم عضو فريق) اسأل عنها أول، لا تخمّن."
    )


def _history_messages(user, message_text: str) -> list[dict]:
    from app.models import AssistantMessage
    rows = (AssistantMessage.query.filter_by(user_id=user.id)
            .order_by(AssistantMessage.id.desc()).limit(HISTORY_MESSAGES + 1).all())
    rows.reverse()
    if rows and rows[-1].role == "user" and (rows[-1].content or "").strip() in (message_text.strip(), "📷 صورة"):
        rows = rows[:-1]
    messages = [{"role": r.role, "content": r.content} for r in rows
                if r.content and getattr(r, "answered_by", None) != "claude_error"]
    while messages and messages[0]["role"] != "user":
        messages.pop(0)
    return messages


def run(user, message_text: str, *, lang: str = "ar", image_bytes: bytes | None = None,
        image_mime: str | None = None, image_url: str | None = None, voice: bool = False) -> str | None:
    """يرجع نص رد الوكيل. None فقط لو الوكيل غير مفعَّل (والمتصل يكمل المسار
    القديم). لو مفعَّل وفشل يرجع رسالة عطل واضحة السبب (تبدأ بـERROR_PREFIX)
    بدل السقوط الصامت لمسار قديم يعطي ردوداً مضلِّلة. لا يرفع أي استثناء."""
    if not is_configured():
        return None
    started = time.monotonic()
    try:
        import base64
        from datetime import date
        import anthropic

        client = _client()
        read_defs, read_registry = _read_tool_defs(user)
        write_defs = [d for d in _WRITE_TOOL_DEFS if _write_tool_allowed(user, d["name"])
                      and (d["name"] != "confirm_action" or _confirm_types())]
        base_tools = read_defs + write_defs
        web_tool = {"type": "web_search_20260209", "name": "web_search", "max_uses": 3}
        system = SYSTEM_PROMPT.format(
            language_instruction=_LANGUAGE_INSTRUCTIONS.get(lang, _LANGUAGE_INSTRUCTIONS["ar"]),
            today=date.today().isoformat(), policy=_policy_text(),
        ) + (VOICE_ADDENDUM if voice else "")
        messages = _history_messages(user, message_text)
        content = []
        if image_bytes:
            content.append({"type": "image", "source": {
                "type": "base64", "media_type": image_mime or "image/jpeg",
                "data": base64.b64encode(image_bytes).decode()}})
        content.append({"type": "text", "text": message_text or "اقرأ هذي الصورة."})
        messages.append({"role": "user", "content": content})

        # تدرّج توافق: لو الخدمة رفضت البحث المدمج (غير مفعَّل بحساب Anthropic)
        # أو معامل الجهد، نكمل بدونه بدل ما يموت الوكيل كله.
        variants = [(True, True), (False, True), (False, False)]
        variant_idx = 0

        ctx = _Ctx(user, message_text, image_url=image_url)
        for _ in range(MAX_TURNS):
            if time.monotonic() - started > TIME_BUDGET_SECONDS:
                return _error_text("انتهت مهلة الرد — جرّب سؤالاً أقصر.")
            while True:
                use_web, use_effort = variants[variant_idx]
                kwargs = dict(model=DEFAULT_MODEL, max_tokens=MAX_OUTPUT_TOKENS, system=system,
                              tools=base_tools + ([web_tool] if use_web else []), messages=messages)
                if use_effort:
                    kwargs["output_config"] = {"effort": "medium"}
                try:
                    response = client.messages.create(**kwargs)
                    break
                except anthropic.BadRequestError:
                    if variant_idx + 1 < len(variants):
                        variant_idx += 1
                        continue
                    raise
            if response.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": response.content})
                continue
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if response.stop_reason != "tool_use" or not tool_uses:
                text = "".join(b.text for b in response.content if b.type == "text").strip()
                return text or _error_text("ما قدر يجهّز رداً — جرّب صياغة ثانية.")
            messages.append({"role": "assistant", "content": response.content})
            results = []
            for block in tool_uses:
                if block.name in _WRITE_TOOLS:
                    out = _WRITE_TOOLS[block.name](ctx, dict(block.input))
                elif block.name in read_registry:
                    try:
                        out = read_registry[block.name](**dict(block.input))
                    except Exception as e:  # أداة قراءة فاشلة لا توقف المحادثة
                        out = {"status": "error", "message": str(e)}
                else:
                    out = {"status": "error", "message": "أداة غير معروفة."}
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": json.dumps(out, ensure_ascii=False, default=str)})
            messages.append({"role": "user", "content": results})
        return _error_text("تجاوز عدد الخطوات المسموح لسؤال واحد — جرّب تقسيم الطلب.")
    except Exception as e:
        try:
            from flask import current_app
            current_app.logger.warning("claude_agent.run failed: %s: %s", type(e).__name__, e)
        except Exception:
            pass
        return _error_text(_describe_error(e))
