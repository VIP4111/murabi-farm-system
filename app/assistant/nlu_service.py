"""
محرك فهم الأسئلة (بند 25 بالمواصفة الرئيسية) — المعمارية الهجينة:

1. **مطابقة كلمات مفتاحية محلية** (`INTENTS` بالأسفل) — تغطي الأسئلة
   المتوقعة عن بيانات المزرعة الحية (`context_service.py`)، كل نية مربوطة
   بصلاحية (نفس نمط `@require_permission` بالشاشات العادية) عشان المساعد
   ما يكشف بيانات المستخدم ما يملك صلاحيتها.
2. **قاعدة المعرفة** (`knowledge_base.py`) — لو ما طابق أي نية، نبحث عن
   إرشاد تشغيلي/بيطري ثابت بالكلمات المفتاحية.
3. **Claude API كامتداد مستقبلي** (`llm_bridge.py`) — لو ما طابق شي محلياً
   ومفتاح `ANTHROPIC_API_KEY` مُفعّل بـ.env، نمرّر السؤال + سياق المزرعة
   الحي + قاعدة المعرفة له. بدون مفتاح، نرجع مباشرة لرد "لم أفهم سؤالك".

**قاعدة محترمة بكل رد يولّده هذا الملف**: "المساعد قرار مو طبيب" — ما فيه
أي حساب جرعة دواء أو تشخيص نهائي بأي مسار هنا.
"""
from dataclasses import dataclass, field
from typing import Callable
from app.extensions import db
from app.models import AssistantMessage
from app.assistant import context_service, knowledge_base, llm_bridge
from app.assistant.text_utils import normalize


@dataclass
class Intent:
    code: str
    keyword_groups: list[list[str]]  # AND بين المجموعات، OR داخل كل مجموعة
    handler: Callable[[object], str]
    permission: str | None = None
    normalized_groups: list[list[str]] = field(default_factory=list, repr=False)

    def __post_init__(self):
        self.normalized_groups = [[normalize(kw) for kw in group] for group in self.keyword_groups]

    def matches(self, normalized_text: str) -> bool:
        return all(any(kw in normalized_text for kw in group) for group in self.normalized_groups)


PERMISSION_DENIED_MSG = "هذا السؤال يحتاج صلاحية غير متوفرة بحسابك حالياً — راجع صاحب المزرعة لو تحتاجها."

HELP_MSG = (
    "أقدر أساعدك بأمثلة زي:\n"
    "- كم عدد الحيوانات بالمزرعة؟\n"
    "- كم رأس حوامل لدينا؟\n"
    "- ما حالة الحاضنات اليوم؟\n"
    "- كم التكلفة اليومية للأعلاف؟\n"
    "- وش التنبيهات الحالية؟\n"
    "- كم عندي مهمة اليوم؟\n"
    "- كم عدد الأمراض المفتوحة؟\n"
    "- إرشادات عن التفقيس، التحصينات، العزل، الشعير المستنبت، أو الأزولا."
)

GREETING_MSG = "وعليكم السلام، أهلاً بك! أنا مساعد مزرعة \"مربي\" الذكي. " + HELP_MSG

FALLBACK_MSG = (
    "ما قدرت أفهم سؤالك بدقة. " + HELP_MSG
)


def _fmt(n: float) -> str:
    return f"{n:,.2f}"


def _handle_greeting(user) -> str:
    return GREETING_MSG


def _handle_help(user) -> str:
    return HELP_MSG


def _handle_herd_count(user) -> str:
    s = context_service.herd_summary()
    lines = [
        f"القطيع النشط حالياً: {s['total_active']} رأس.",
        f"المجترات (غنم/ماعز): {s['ruminants_total']} — ذكور {s['ruminants_male']}، إناث {s['ruminants_female']}.",
    ]
    if s["ostrich_total"]:
        lines.append(f"النعام: {s['ostrich_total']} — ذكور {s['ostrich_male']}، إناث {s['ostrich_female']}.")
    return "\n".join(lines)


def _handle_pregnant(user) -> str:
    s = context_service.pregnant_summary()
    if s["count"] == 0:
        return "ما فيه حالياً إناث حوامل مسجّلة بالنظام."
    nums = "، ".join(s["animal_numbers"])
    extra = f" (وغيرهم حتى {s['count']})" if s["count"] > len(s["animal_numbers"]) else ""
    reply = f"عدد الإناث الحوامل حالياً: {s['count']} رأس: {nums}{extra}."
    if s["near_birth_count"]:
        reply += f"\nمنهم {s['near_birth_count']} قريبين من الولادة خلال 30 يوم القادمة."
    return reply


def _handle_near_birth(user) -> str:
    s = context_service.pregnant_summary()
    if s["near_birth_count"] == 0:
        return "ما فيه حيوانات قريبة من الولادة خلال 30 يوم القادمة حالياً."
    nums = "، ".join(s["near_birth_numbers"])
    return f"عندك {s['near_birth_count']} رأس قريب من الولادة خلال 30 يوم القادمة: {nums}."


def _handle_ostrich(user) -> str:
    s = context_service.ostrich_summary()
    line1 = f"الحاضنات: {s['incubators_total']} حاضنة فعّالة، مشغولة حالياً: {s['incubators_occupied']}"
    if s["capacity_total"]:
        line1 += f" (سعة إجمالية {s['capacity_total']} بيضة)."
    else:
        line1 += "."
    line2 = f"البيض: {s['eggs_pending']} قيد الحضانة، {s['eggs_hatched']} فقست، {s['eggs_failed']} فشلت."
    return line1 + "\n" + line2


def _handle_feed_location(user) -> str:
    return (
        "مخزون العلف تلقاه بشاشة \"الأعلاف\" من القائمة الرئيسية (/feed/items)، "
        "أو من شاشة \"متابعة مبسّطة\" ← المخزون ← الأعلاف لو تبي عرض مبسّط بخط كبير."
    )


def _handle_feed_cost(user) -> str:
    s = context_service.feed_cost_summary()
    if not s["has_active_plans"]:
        return "ما فيه خطط تغذية فعّالة حالياً بشاشة العلف، فما أقدر أحسب التكلفة اليومية."
    lines = [f"التكلفة اليومية التقديرية للعلف: {_fmt(s['total_daily_cost'])} (تقدير شهري ≈ {_fmt(s['total_monthly_estimate'])})."]
    for b in s["barn_breakdown"][:5]:
        lines.append(f"- {b['barn_name']} ({b['head_count']} رأس، وصفة {b['ration_name']}): {_fmt(b['daily_cost'])}")
    return "\n".join(lines)


def _handle_alerts(user) -> str:
    s = context_service.alerts_summary(limit=5)
    if s["total"] == 0:
        return "ما فيه تنبيهات حالياً — كل شي تمام."
    lines = [f"عندك {s['total']} تنبيه ({s['urgent_total']} عاجل). أهمها:"]
    for a in s["top"]:
        detail = f" — {a['detail']}" if a["detail"] else ""
        lines.append(f"- {a['icon']} {a['label']}{detail}")
    lines.append("افتح شاشة التنبيهات لعرض القائمة كاملة.")
    return "\n".join(lines)


def _handle_tasks(user) -> str:
    s = context_service.my_tasks_summary(user)
    if s["count"] == 0:
        return "ما عندك مهام مفتوحة حالياً."
    lines = [f"عندك {s['count']} مهمة مفتوحة:"]
    for t in s["items"]:
        lock = " 🔒 مقفلة" if t["locked"] else ""
        due = f" (موعدها {t['due_date']})" if t["due_date"] else ""
        lines.append(f"- {t['title']}{due}{lock}")
    return "\n".join(lines)


def _handle_diseases(user) -> str:
    s = context_service.disease_summary()
    if s["count"] == 0:
        return "ما فيه أمراض مفتوحة حالياً — الوضع الصحي للقطيع سليم."
    lines = [f"عندك {s['count']} حالة مرض مفتوحة:"]
    for d in s["items"]:
        lines.append(f"- {d['animal_no']}: {d['disease_name']} (مفتوح منذ {d['days_open']} يوم)")
    return "\n".join(lines)


def _handle_vaccinations_due(user) -> str:
    s = context_service.vaccinations_due_summary()
    if s["count"] == 0:
        return "ما فيه تحصينات مستحقة أو متأخرة حالياً."
    lines = [f"عندك {s['count']} تحصين مستحق/متأخر ({s['overdue_count']} متأخر فعلياً):"]
    for a in s["items"]:
        lines.append(f"- {a['label']} — {a['detail']}")
    return "\n".join(lines)


def _handle_finance(user) -> str:
    s = context_service.finance_summary()
    net_line = f"الصافي (بدون الديون): {_fmt(s['net'])}"
    if s["net_percent"] is not None:
        net_line += f" — نسبة الربح: {s['net_percent']:g}%"
    lines = [
        f"ملخص المالية لشهر {s['month_name']}:",
        f"مبيعات: {_fmt(s['sales'])} | مشتريات: {_fmt(s['purchases'])} | مصروفات: {_fmt(s['expenses'])}",
        net_line,
    ]
    if s["debt_outstanding"]:
        lines.append(f"دين مستحق حالياً: {_fmt(s['debt_outstanding'])}")
    return "\n".join(lines)


# ترتيب القائمة مهم: النيات الأكثر تحديداً أولاً، والعامة (herd_count) قرب
# النهاية — عشان "كم عدد الحاضنات" مثلاً يطابق نية النعام قبل ما يوصل لعدّاد
# الحيوانات العام.
INTENTS: list[Intent] = [
    Intent("greeting", [["السلام عليكم", "مرحبا", "هلا", "صباح الخير", "مساء الخير"]], _handle_greeting),
    Intent("help", [["مساعدة", "ماذا تستطيع", "شو تقدر تسوي", "ما هي قدراتك", "اوامر"]], _handle_help),
    Intent("near_birth", [["قريب الولادة", "قرب الولادة", "بدها تولد", "متى تلد", "ولادات قريبة", "ولادات متوقعة"]],
           _handle_near_birth, permission="animals.view"),
    Intent("pregnant", [["حوامل", "حامل", "حمل مؤكد"]], _handle_pregnant, permission="animals.view"),
    Intent("ostrich", [["حاضنة", "حاضنات", "تفقيس", "بيض النعام", "النعام"]], _handle_ostrich, permission="repro.view"),
    Intent("feed_location", [["علف", "اعلاف", "أعلاف"], ["وين", "أين", "فين", "مكان", "لقى", "اجد", "أجد"]],
           _handle_feed_location, permission="feed.view"),
    Intent("feed_cost", [["علف", "اعلاف", "أعلاف"], ["تكلفة", "مصروف", "كم"]], _handle_feed_cost, permission="feed.view"),
    Intent("alerts", [["تنبيه", "تنبيهات", "انذار", "إنذار"]], _handle_alerts, permission="animals.view"),
    Intent("tasks", [["مهامي", "مهمتي", "مهام اليوم", "مهامي اليوم"]], _handle_tasks, permission="tasks.view_own"),
    Intent("diseases", [["امراض مفتوحة", "مرض مفتوح", "حيوانات مريضة", "كم مريض"]], _handle_diseases, permission="health.view"),
    Intent("vaccinations_due", [["تحصين مستحق", "تطعيم مستحق", "تحصينات مستحقة", "موعد تحصين", "تحصين متاخر"]],
           _handle_vaccinations_due, permission="health.view"),
    Intent("finance", [["المبيعات", "الارباح", "صافي الربح", "الوضع المالي", "المصروفات هذا الشهر",
                         "نسبة الربح", "نسبة ربحي", "كم ربحي", "نسبة ارباحي"]],
           _handle_finance, permission="finance.full.manage"),
    Intent("herd_count", [["كم", "عدد"], ["حيوان", "راس", "رأس", "رؤوس", "قطيع", "حلال"]],
           _handle_herd_count, permission="animals.view"),
]


def _build_llm_context(user) -> str:
    """ملخص نصي مختصر لبيانات المزرعة الحية، يُمرَّر لـClaude API لو
    فُعّل مستقبلاً — يحترم صلاحيات المستخدم الحالي (نفس فحص النيات)."""
    parts = []
    if user.has_permission("animals.view"):
        h = context_service.herd_summary()
        parts.append(f"القطيع: {h['total_active']} رأس نشط (مجترات {h['ruminants_total']}، نعام {h['ostrich_total']}).")
        p = context_service.pregnant_summary()
        parts.append(f"حوامل: {p['count']}، قريبات من الولادة: {p['near_birth_count']}.")
    if user.has_permission("health.view"):
        d = context_service.disease_summary()
        parts.append(f"أمراض مفتوحة: {d['count']}.")
    if user.has_permission("feed.view"):
        f = context_service.feed_cost_summary()
        if f["has_active_plans"]:
            parts.append(f"تكلفة العلف اليومية التقديرية: {_fmt(f['total_daily_cost'])}.")
    return "\n".join(parts) if parts else "لا توجد بيانات متاحة لصلاحيات هذا المستخدم."


def answer(user, message_text: str) -> dict:
    """المنطق الصافي بدون أي حفظ بقاعدة البيانات — يرجع
    {"reply", "intent_code", "answered_by"}."""
    normalized = normalize(message_text)

    for intent in INTENTS:
        if intent.matches(normalized):
            if intent.permission and not user.has_permission(intent.permission):
                return {"reply": PERMISSION_DENIED_MSG, "intent_code": intent.code, "answered_by": "local"}
            return {"reply": intent.handler(user), "intent_code": intent.code, "answered_by": "local"}

    kb_hits = knowledge_base.search(normalized, limit=1)
    if kb_hits:
        entry = kb_hits[0]
        return {"reply": f"**{entry.title}**\n\n{entry.body}", "intent_code": f"kb:{entry.code}", "answered_by": "local"}

    llm_reply = llm_bridge.ask(message_text, _build_llm_context(user))
    if llm_reply:
        return {"reply": llm_reply, "intent_code": None, "answered_by": "llm"}

    return {"reply": FALLBACK_MSG, "intent_code": None, "answered_by": "local"}


def ask_and_record(user, message_text: str) -> AssistantMessage:
    """يسجّل رسالة المستخدم والرد بجدول `AssistantMessage` ويرجع صف الرد."""
    user_msg = AssistantMessage(user_id=user.id, role="user", content=message_text)
    db.session.add(user_msg)

    result = answer(user, message_text)
    assistant_msg = AssistantMessage(
        user_id=user.id, role="assistant", content=result["reply"],
        intent_code=result["intent_code"], answered_by=result["answered_by"],
    )
    db.session.add(assistant_msg)
    db.session.commit()
    return assistant_msg
