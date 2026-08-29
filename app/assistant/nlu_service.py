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
from app.assistant.translations import tr, lang_for


@dataclass
class Intent:
    code: str
    keyword_groups: list[list[str]]  # AND بين المجموعات، OR داخل كل مجموعة
    handler: Callable[[object, str], str]
    permission: str | None = None
    normalized_groups: list[list[str]] = field(default_factory=list, repr=False)

    def __post_init__(self):
        self.normalized_groups = [[normalize(kw) for kw in group] for group in self.keyword_groups]

    def matches(self, normalized_text: str) -> bool:
        return all(any(kw in normalized_text for kw in group) for group in self.normalized_groups)


def PERMISSION_DENIED_MSG(lang="ar"):
    return tr("permission_denied", lang)


def HELP_MSG(lang="ar"):
    return tr("help", lang)


def GREETING_MSG(lang="ar"):
    return tr("greeting", lang) + HELP_MSG(lang)


def FALLBACK_MSG(lang="ar"):
    return tr("fallback_prefix", lang) + HELP_MSG(lang)


def _fmt(n: float) -> str:
    return f"{n:,.2f}"


def _handle_greeting(user, lang) -> str:
    return GREETING_MSG(lang)


def _handle_help(user, lang) -> str:
    return HELP_MSG(lang)


def _handle_herd_count(user, lang) -> str:
    s = context_service.herd_summary()
    lines = [
        tr("herd_count_active", lang, total=s["total_active"]),
        tr("herd_count_ruminants", lang, total=s["ruminants_total"], male=s["ruminants_male"], female=s["ruminants_female"]),
    ]
    if s["ostrich_total"]:
        lines.append(tr("herd_count_ostrich", lang, total=s["ostrich_total"], male=s["ostrich_male"], female=s["ostrich_female"]))
    return "\n".join(lines)


def _handle_pregnant(user, lang) -> str:
    s = context_service.pregnant_summary()
    if s["count"] == 0:
        return tr("no_pregnant", lang)
    nums = "، ".join(s["animal_numbers"])
    extra = tr("pregnant_extra", lang, count=s["count"]) if s["count"] > len(s["animal_numbers"]) else ""
    reply = tr("pregnant_count", lang, count=s["count"], names=nums, extra=extra)
    if s["near_birth_count"]:
        reply += "\n" + tr("pregnant_near_birth_note", lang, count=s["near_birth_count"])
    return reply


def _handle_near_birth(user, lang) -> str:
    s = context_service.pregnant_summary()
    if s["near_birth_count"] == 0:
        return tr("no_near_birth", lang)
    nums = "، ".join(s["near_birth_numbers"])
    return tr("near_birth_count", lang, count=s["near_birth_count"], names=nums)


def _handle_ostrich(user, lang) -> str:
    s = context_service.ostrich_summary()
    line1 = tr("ostrich_line1", lang, total=s["incubators_total"], occupied=s["incubators_occupied"])
    line1 += tr("ostrich_capacity", lang, capacity=s["capacity_total"]) if s["capacity_total"] else "."
    line2 = tr("ostrich_eggs", lang, pending=s["eggs_pending"], hatched=s["eggs_hatched"], failed=s["eggs_failed"])
    return line1 + "\n" + line2


def _handle_feed_location(user, lang) -> str:
    return tr("feed_location", lang)


def _handle_feed_cost(user, lang) -> str:
    s = context_service.feed_cost_summary()
    if not s["has_active_plans"]:
        return tr("feed_cost_none", lang)
    lines = [tr("feed_cost_total", lang, daily=_fmt(s["total_daily_cost"]), monthly=_fmt(s["total_monthly_estimate"]))]
    for b in s["barn_breakdown"][:5]:
        lines.append(tr("feed_cost_barn_line", lang, barn=b["barn_name"], count=b["head_count"],
                         ration=b["ration_name"], cost=_fmt(b["daily_cost"])))
    return "\n".join(lines)


def _handle_alerts(user, lang) -> str:
    s = context_service.alerts_summary(limit=5)
    if s["total"] == 0:
        return tr("alerts_none", lang)
    lines = [tr("alerts_count", lang, total=s["total"], urgent=s["urgent_total"])]
    for a in s["top"]:
        detail = f" — {a['detail']}" if a["detail"] else ""
        lines.append(f"- {a['icon']} {a['label']}{detail}")
    lines.append(tr("alerts_footer", lang))
    return "\n".join(lines)


def _handle_today_plan(user, lang) -> str:
    """"شنو أسوي اليوم؟" (بند إضافي 274، طلبك الصريح) — يجمع مهامك
    المفتوحة الحالية (`tasks.view_own`، متاحة لكل عضو فريق فعّال) +
    أهم التنبيهات العاجلة (`animals.view` — لو ما عندك هالصلاحية،
    يظهر قسم المهام بس، بدون خطأ). مو نية جديدة تحسب شي إضافي —
    تجميع لنيتين موجودتين أصلاً (`tasks`/`alerts`) بردٍ واحد مختصر،
    عشان ما تحتاج تسأل سؤالين منفصلين."""
    parts = []

    tasks = context_service.my_tasks_summary(user)
    if tasks["count"] == 0:
        parts.append(tr("today_no_tasks", lang))
    else:
        lines = [tr("today_tasks_header", lang, count=tasks["count"])]
        for t in tasks["items"]:
            lock = tr("task_locked", lang) if t["locked"] else ""
            due = tr("task_due", lang, due=t["due_date"]) if t["due_date"] else ""
            lines.append(f"- {t['title']}{due}{lock}")
        parts.append("\n".join(lines))

    if user.has_permission("animals.view"):
        alerts = context_service.alerts_summary(limit=3)
        if alerts["urgent_total"]:
            lines = [tr("today_urgent_header", lang, urgent=alerts["urgent_total"], total=alerts["total"])]
            for a in alerts["top"]:
                if a["urgent"]:
                    lines.append(f"- {a['icon']} {a['label']}")
            parts.append("\n".join(lines))
        elif alerts["total"]:
            parts.append(tr("today_nonurgent_note", lang, total=alerts["total"]))

    return "\n".join(parts)


def _handle_tasks(user, lang) -> str:
    s = context_service.my_tasks_summary(user)
    if s["count"] == 0:
        return tr("tasks_none", lang)
    lines = [tr("tasks_count", lang, count=s["count"])]
    for t in s["items"]:
        lock = tr("task_locked", lang) if t["locked"] else ""
        due = tr("task_due", lang, due=t["due_date"]) if t["due_date"] else ""
        lines.append(f"- {t['title']}{due}{lock}")
    return "\n".join(lines)


def _handle_diseases(user, lang) -> str:
    s = context_service.disease_summary()
    if s["count"] == 0:
        return tr("diseases_none", lang)
    lines = [tr("diseases_count", lang, count=s["count"])]
    for d in s["items"]:
        lines.append(tr("disease_line", lang, animal=d["animal_no"], name=d["disease_name"], days=d["days_open"]))
    return "\n".join(lines)


def _handle_vaccinations_due(user, lang) -> str:
    s = context_service.vaccinations_due_summary()
    if s["count"] == 0:
        return tr("vaccinations_none", lang)
    lines = [tr("vaccinations_count", lang, count=s["count"], overdue=s["overdue_count"])]
    for a in s["items"]:
        lines.append(tr("vaccination_line", lang, label=a["label"], detail=a["detail"]))
    return "\n".join(lines)


def _handle_finance(user, lang) -> str:
    s = context_service.finance_summary()
    net_line = tr("finance_net", lang, net=_fmt(s["net"]))
    if s["net_percent"] is not None:
        net_line += tr("finance_net_percent", lang, percent=f"{s['net_percent']:g}")
    lines = [
        tr("finance_header", lang, month=s["month_name"]),
        tr("finance_line", lang, sales=_fmt(s["sales"]), purchases=_fmt(s["purchases"]), expenses=_fmt(s["expenses"])),
        net_line,
    ]
    if s["debt_outstanding"]:
        lines.append(tr("finance_debt", lang, debt=_fmt(s["debt_outstanding"])))
    return "\n".join(lines)


# ترتيب القائمة مهم: النيات الأكثر تحديداً أولاً، والعامة (herd_count) قرب
# النهاية — عشان "كم عدد الحاضنات" مثلاً يطابق نية النعام قبل ما يوصل لعدّاد
# الحيوانات العام.
INTENTS: list[Intent] = [
    Intent("greeting", [["السلام عليكم", "مرحبا", "هلا", "صباح الخير", "مساء الخير",
                          "hello", "hi", "good morning", "good evening",
                          "ሰላም", "እንደምን አደሩ",
                          "नमस्ते", "नमस्कार"]], _handle_greeting),
    Intent("help", [["مساعدة", "ماذا تستطيع", "شو تقدر تسوي", "ما هي قدراتك", "اوامر",
                      "help", "what can you do",
                      "እርዳታ", "ምን ማድረግ ትችላለህ",
                      "मदद", "आप क्या कर सकते हैं"]], _handle_help),
    Intent("near_birth", [["قريب الولادة", "قرب الولادة", "بدها تولد", "متى تلد", "ولادات قريبة", "ولادات متوقعة",
                            "near delivery", "about to give birth", "due date",
                            "ለመውለድ ተቃርበ", "የመውለጃ ቀን",
                            "प्रसव के करीब", "प्रसव तिथि"]],
           _handle_near_birth, permission="animals.view"),
    Intent("pregnant", [["حوامل", "حامل", "حمل مؤكد", "pregnant", "pregnancy", "እርጉዝ", "गर्भवती"]],
           _handle_pregnant, permission="animals.view"),
    Intent("ostrich", [["حاضنة", "حاضنات", "تفقيس", "بيض النعام", "النعام",
                         "incubator", "hatching", "ostrich egg", "ostrich",
                         "ማቀፊያ", "መፈልፈል", "ሰጎን",
                         "इनक्यूबेटर", "हैचिंग", "शुतुरमुर्ग"]],
           _handle_ostrich, permission="repro.view"),
    Intent("feed_location", [["علف", "اعلاف", "أعلاف", "feed", "fodder", "መኖ", "चारा"],
                              ["وين", "أين", "فين", "مكان", "لقى", "اجد", "أجد",
                               "where", "location", "find",
                               "የት", "የት አለ",
                               "कहाँ", "कहां"]],
           _handle_feed_location, permission="feed.view"),
    Intent("feed_cost", [["علف", "اعلاف", "أعلاف", "feed", "fodder", "መኖ", "चारा"],
                          ["تكلفة", "مصروف", "كم", "cost", "how much", "ወጪ", "ስንት", "लागत", "कितना"]],
           _handle_feed_cost, permission="feed.view"),
    Intent("today_plan", [["ماذا اسوي اليوم", "وش اسوي اليوم", "شنو اسوي اليوم", "ايش اسوي اليوم",
                            "ماذا علي فعله اليوم", "شنو برنامجي اليوم", "خطة اليوم", "وش برنامجي اليوم",
                            "what should i do today", "today's plan", "my plan today",
                            "ዛሬ ምን ማድረግ አለብኝ", "የዛሬ እቅድ",
                            "आज मुझे क्या करना चाहिए", "आज की योजना"]],
           _handle_today_plan, permission="tasks.view_own"),
    Intent("alerts", [["تنبيه", "تنبيهات", "انذار", "إنذار", "alert", "alerts", "notification",
                        "ማንቂያ", "ማስጠንቀቂያ", "अलर्ट", "चेतावनी"]],
           _handle_alerts, permission="animals.view"),
    Intent("tasks", [["مهامي", "مهمتي", "مهام اليوم", "مهامي اليوم",
                       "my tasks", "today's tasks",
                       "የእኔ ተግባራት", "የዛሬ ተግባራት",
                       "मेरे कार्य", "आज के कार्य"]],
           _handle_tasks, permission="tasks.view_own"),
    Intent("diseases", [["امراض مفتوحة", "مرض مفتوح", "حيوانات مريضة", "كم مريض",
                          "open disease", "sick animals",
                          "ክፍት በሽታ", "የታመሙ እንስሳት",
                          "खुला रोग", "बीमार जानवर"]],
           _handle_diseases, permission="health.view"),
    Intent("vaccinations_due", [["تحصين مستحق", "تطعيم مستحق", "تحصينات مستحقة", "موعد تحصين", "تحصين متاخر",
                                  "vaccination due", "overdue vaccination",
                                  "የደረሰ ክትባት", "የዘገየ ክትባት",
                                  "देय टीकाकरण", "विलंबित टीकाकरण"]],
           _handle_vaccinations_due, permission="health.view"),
    Intent("finance", [["المبيعات", "الارباح", "صافي الربح", "الوضع المالي", "المصروفات هذا الشهر",
                         "نسبة الربح", "نسبة ربحي", "كم ربحي", "نسبة ارباحي",
                         "sales", "profit", "net profit", "financial status", "profit percentage",
                         "ሽያጭ", "ትርፍ", "የፋይናንስ ሁኔታ",
                         "बिक्री", "लाभ", "वित्तीय स्थिति"]],
           _handle_finance, permission="finance.full.manage"),
    Intent("herd_count", [["كم", "عدد", "how many", "how much", "count", "ስንት", "कितने", "कितना"],
                           ["حيوان", "راس", "رأس", "رؤوس", "قطيع", "حلال",
                            "animal", "head", "herd",
                            "እንስሳት", "ራስ", "መንጋ",
                            "जानवर", "सिर", "झुंड"]],
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


def answer(user, message_text: str, lang: str | None = None) -> dict:
    """المنطق الصافي بدون أي حفظ بقاعدة البيانات — يرجع
    {"reply", "intent_code", "answered_by"}.

    ``lang`` (بند إضافي 275، طلبك الصريح "كل شي دفعة وحدة" لما سألت
    هل المساعد بعدة لغات) — افتراضياً `user.language` (نفس حقل اللغة
    المستخدم أصلاً بـ8 شاشات ميدانية)، مقيّد بـ{ar, en, am, hi}."""
    lang = lang or lang_for(user)
    normalized = normalize(message_text)

    for intent in INTENTS:
        if intent.matches(normalized):
            if intent.permission and not user.has_permission(intent.permission):
                return {"reply": PERMISSION_DENIED_MSG(lang), "intent_code": intent.code, "answered_by": "local"}
            return {"reply": intent.handler(user, lang), "intent_code": intent.code, "answered_by": "local"}

    kb_hits = knowledge_base.search(normalized, limit=1)
    if kb_hits:
        entry = kb_hits[0]
        title, body = knowledge_base.localized_entry(entry, lang)
        return {"reply": f"**{title}**\n\n{body}", "intent_code": f"kb:{entry.code}", "answered_by": "local"}

    # بند إضافي 297 — Gemini بأدوات القراءة الذكية يُجرَّب أولاً (يقرأ
    # بيانات حية عبر استدعاء أدوات فعلية بدل نص سياق ثابت مجمَّع مسبقاً)؛
    # لو غير مفعَّل أو فشل، نرجع لجسر Claude النصي القديم كما كان تماماً.
    tools_reply = llm_bridge.ask_with_tools(message_text, user, lang=lang)
    if tools_reply:
        return {"reply": tools_reply, "intent_code": None, "answered_by": "llm_tools"}

    llm_reply = llm_bridge.ask(message_text, _build_llm_context(user), lang=lang)
    if llm_reply:
        return {"reply": llm_reply, "intent_code": None, "answered_by": "llm"}

    return {"reply": FALLBACK_MSG(lang), "intent_code": None, "answered_by": "local"}


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


def answer_with_image(user, message_text: str, image_bytes: bytes, mime_type: str,
                       lang: str | None = None) -> dict:
    """بند إضافي 305 — صورة مرفقة تروح مباشرة لـGemini بالرؤية، بدون
    محرك النيات المحلي أو قاعدة المعرفة (كلاهما نص بس، ما يفهمان صوراً
    أصلاً). لو Gemini غير مفعَّل، رسالة واضحة بدل fallback عام مضلِّل."""
    lang = lang or lang_for(user)
    reply = llm_bridge.ask_with_image(message_text, image_bytes, mime_type, lang=lang)
    if reply:
        return {"reply": reply, "intent_code": None, "answered_by": "llm_vision"}
    return {
        "reply": tr("vision_unavailable", lang),
        "intent_code": None, "answered_by": "local",
    }


def ask_and_record_with_image(user, message_text: str, image_bytes: bytes, mime_type: str,
                               image_url: str | None) -> AssistantMessage:
    """نفس `ask_and_record` بالضبط بس مع صورة مرفقة — رسالة المستخدم
    تُسجَّل مع `image_url` (رابط دائم، للعرض بسجل المحادثة فقط)، بينما
    التحليل الفعلي يستخدم البايتات الخام مباشرة (بدون تحميل الرابط
    مرة ثانية)."""
    user_msg = AssistantMessage(user_id=user.id, role="user", content=message_text or "📷 صورة",
                                 image_url=image_url)
    db.session.add(user_msg)

    result = answer_with_image(user, message_text, image_bytes, mime_type)
    assistant_msg = AssistantMessage(
        user_id=user.id, role="assistant", content=result["reply"],
        intent_code=result["intent_code"], answered_by=result["answered_by"],
    )
    db.session.add(assistant_msg)
    db.session.commit()
    return assistant_msg
