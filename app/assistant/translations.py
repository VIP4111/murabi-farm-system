"""ترجمات ردود المساعد الذكي "الحية" (بند إضافي 275، طلبك الصريح بعد
سؤالك "هل المساعد بعدة لغات") — عربي المصدر الأصلي، أضفنا 3 لغات ثانية
(نفس اللغات المدعومة أصلاً بالشاشات الميدانية: إنجليزي/أمهري/هندي).

**نطاق هذا الملف بالتحديد**: الرسائل الثابتة + كل ردود النيات الحية
(`_handle_*` بـ`nlu_service.py`) — الجزء اللي يحسب من بياناتك الفعلية.
قاعدة المعرفة (`knowledge_base.py`، 120+ بند إرشادي) لها ملف ترجمة
منفصل (`kb_translations.py`) بما إنها أضخم بكثير وتُترجم على دفعات.

**البنية**: `T[key][lang]` = نص جاهز أو قالب `.format()`. `tr(key, lang,
**kwargs)` يرجع النص المترجم، أو العربي تلقائياً لو اللغة/المفتاح
غير موجودة (تغطية تدريجية، صفر كسر لأي مسار قديم)."""

SUPPORTED_LANGS = {"ar", "en", "am", "hi"}


def lang_for(user) -> str:
    lang = getattr(user, "language", None) or "ar"
    return lang if lang in SUPPORTED_LANGS else "ar"


T: dict[str, dict[str, str]] = {
    "greeting": {
        "ar": "وعليكم السلام، أهلاً بك! أنا مساعد مزرعة \"مربي\" الذكي. ",
        "en": "Hello, welcome! I'm the smart assistant for the \"Murabi\" farm system. ",
        "am": "ሰላም እንኳን ደህና መጡ! እኔ የ«ሙረቢ» እርሻ ስርዓት ብልህ ረዳት ነኝ። ",
        "hi": "नमस्ते, स्वागत है! मैं \"मुरबी\" फार्म सिस्टम का स्मार्ट सहायक हूँ। ",
    },
    "help": {
        "ar": (
            "أقدر أساعدك بأمثلة زي:\n"
            "- ماذا علي فعله اليوم؟\n"
            "- كم عدد الحيوانات بالمزرعة؟\n"
            "- كم رأس حوامل لدينا؟\n"
            "- ما حالة الحاضنات اليوم؟\n"
            "- كم التكلفة اليومية للأعلاف؟\n"
            "- وش التنبيهات الحالية؟\n"
            "- كم عندي مهمة اليوم؟\n"
            "- كم عدد الأمراض المفتوحة؟\n"
            "- إرشادات عن التفقيس، التحصينات، العزل، الشعير المستنبت، أو الأزولا."
        ),
        "en": (
            "I can help with examples like:\n"
            "- What should I do today?\n"
            "- How many animals are on the farm?\n"
            "- How many pregnant females do we have?\n"
            "- What's the incubator status today?\n"
            "- What's the daily feed cost?\n"
            "- What are the current alerts?\n"
            "- How many tasks do I have today?\n"
            "- How many open disease cases?\n"
            "- Guidance on hatching, vaccinations, isolation, sprouted barley, or azolla."
        ),
        "am": (
            "እንደዚህ ባሉ ምሳሌዎች ልረዳዎት እችላለሁ:\n"
            "- ዛሬ ምን ማድረግ አለብኝ?\n"
            "- በእርሻው ስንት እንስሳት አሉ?\n"
            "- ስንት እርጉዝ ሴቶች አሉን?\n"
            "- የመፈልፈያዎቹ ሁኔታ ዛሬ ምንድን ነው?\n"
            "- የዕለታዊ መኖ ወጪ ስንት ነው?\n"
            "- የአሁኑ ማንቂያዎች ምንድን ናቸው?\n"
            "- ዛሬ ስንት ተግባራት አሉኝ?\n"
            "- ስንት ክፍት የበሽታ ጉዳዮች አሉ?\n"
            "- ስለ መፈልፈል፣ ክትባቶች፣ ማግለል፣ የበቀለ ገብስ ወይም አዞላ መመሪያ።"
        ),
        "hi": (
            "मैं इन उदाहरणों से मदद कर सकता हूँ:\n"
            "- आज मुझे क्या करना चाहिए?\n"
            "- फार्म पर कितने जानवर हैं?\n"
            "- हमारे पास कितनी गर्भवती मादाएं हैं?\n"
            "- आज इनक्यूबेटर की स्थिति क्या है?\n"
            "- दैनिक चारे की लागत कितनी है?\n"
            "- वर्तमान अलर्ट क्या हैं?\n"
            "- आज मेरे पास कितने कार्य हैं?\n"
            "- कितने खुले रोग मामले हैं?\n"
            "- हैचिंग, टीकाकरण, आइसोलेशन, अंकुरित जौ, या एज़ोला पर मार्गदर्शन।"
        ),
    },
    "permission_denied": {
        "ar": "هذا السؤال يحتاج صلاحية غير متوفرة بحسابك حالياً — راجع صاحب المزرعة لو تحتاجها.",
        "en": "This question needs a permission your account doesn't currently have — ask the farm owner if you need it.",
        "am": "ይህ ጥያቄ አሁን በመለያዎ ውስጥ የሌለ ፈቃድ ይፈልጋል — ካስፈለገዎት የእርሻ ባለቤቱን ያነጋግሩ።",
        "hi": "इस सवाल के लिए एक अनुमति चाहिए जो अभी आपके खाते में नहीं है — ज़रूरत हो तो फार्म मालिक से संपर्क करें।",
    },
    "fallback_prefix": {
        "ar": "ما قدرت أفهم سؤالك بدقة. ",
        "en": "I couldn't quite understand your question. ",
        "am": "ጥያቄዎን በትክክል መረዳት አልቻልኩም። ",
        "hi": "मैं आपका सवाल ठीक से समझ नहीं पाया। ",
    },
    "herd_count_active": {
        "ar": "القطيع النشط حالياً: {total} رأس.",
        "en": "Current active herd: {total} head.",
        "am": "አሁን ያለው ንቁ መንጋ: {total} ራስ.",
        "hi": "वर्तमान सक्रिय झुंड: {total} सिर।",
    },
    "herd_count_ruminants": {
        "ar": "المجترات (غنم/ماعز): {total} — ذكور {male}، إناث {female}.",
        "en": "Ruminants (sheep/goats): {total} — males {male}, females {female}.",
        "am": "አፍላቂ እንስሳት (በግ/ፍየል): {total} — ወንድ {male}፣ ሴት {female}።",
        "hi": "जुगाली करने वाले (भेड़/बकरी): {total} — नर {male}, मादा {female}।",
    },
    "herd_count_ostrich": {
        "ar": "النعام: {total} — ذكور {male}، إناث {female}.",
        "en": "Ostriches: {total} — males {male}, females {female}.",
        "am": "ሰጎን: {total} — ወንድ {male}፣ ሴት {female}።",
        "hi": "शुतुरमुर्ग: {total} — नर {male}, मादा {female}।",
    },
    "no_pregnant": {
        "ar": "ما فيه حالياً إناث حوامل مسجّلة بالنظام.",
        "en": "There are currently no pregnant females recorded in the system.",
        "am": "አሁን በስርዓቱ የተመዘገበ እርጉዝ ሴት የለም።",
        "hi": "फिलहाल सिस्टम में कोई गर्भवती मादा दर्ज नहीं है।",
    },
    "pregnant_count": {
        "ar": "عدد الإناث الحوامل حالياً: {count} رأس: {names}{extra}.",
        "en": "Currently pregnant females: {count} head: {names}{extra}.",
        "am": "አሁን እርጉዝ የሆኑ ሴቶች ብዛት: {count} ራስ: {names}{extra}።",
        "hi": "वर्तमान गर्भवती मादाएं: {count} सिर: {names}{extra}।",
    },
    "pregnant_extra": {
        "ar": " (وغيرهم حتى {count})",
        "en": " (and others, up to {count})",
        "am": " (እና ሌሎች እስከ {count})",
        "hi": " (और अन्य, {count} तक)",
    },
    "pregnant_near_birth_note": {
        "ar": "منهم {count} قريبين من الولادة خلال 30 يوم القادمة.",
        "en": "{count} of them are near delivery within the next 30 days.",
        "am": "ከነሱ {count} በሚቀጥሉት 30 ቀናት ውስጥ ለመውለድ ተቃርበዋል።",
        "hi": "उनमें से {count} अगले 30 दिनों में प्रसव के करीब हैं।",
    },
    "no_near_birth": {
        "ar": "ما فيه حيوانات قريبة من الولادة خلال 30 يوم القادمة حالياً.",
        "en": "No animals are currently near delivery within the next 30 days.",
        "am": "አሁን በሚቀጥሉት 30 ቀናት ውስጥ ለመውለድ የተቃረበ እንስሳ የለም።",
        "hi": "फिलहाल अगले 30 दिनों में प्रसव के करीब कोई जानवर नहीं है।",
    },
    "near_birth_count": {
        "ar": "عندك {count} رأس قريب من الولادة خلال 30 يوم القادمة: {names}.",
        "en": "You have {count} head near delivery within the next 30 days: {names}.",
        "am": "በሚቀጥሉት 30 ቀናት ውስጥ ለመውለድ የተቃረቡ {count} ራሶች አሉዎት: {names}።",
        "hi": "अगले 30 दिनों में प्रसव के करीब आपके पास {count} सिर हैं: {names}।",
    },
    "ostrich_line1": {
        "ar": "الحاضنات: {total} حاضنة فعّالة، مشغولة حالياً: {occupied}",
        "en": "Incubators: {total} active, currently occupied: {occupied}",
        "am": "ማቀፊያዎች: {total} ንቁ፣ አሁን ተይዘዋል: {occupied}",
        "hi": "इनक्यूबेटर: {total} सक्रिय, वर्तमान में व्याप्त: {occupied}",
    },
    "ostrich_capacity": {
        "ar": " (سعة إجمالية {capacity} بيضة).",
        "en": " (total capacity {capacity} eggs).",
        "am": " (ጠቅላላ አቅም {capacity} እንቁላል)።",
        "hi": " (कुल क्षमता {capacity} अंडे)।",
    },
    "ostrich_eggs": {
        "ar": "البيض: {pending} قيد الحضانة، {hatched} فقست، {failed} فشلت.",
        "en": "Eggs: {pending} incubating, {hatched} hatched, {failed} failed.",
        "am": "እንቁላል: {pending} በመታቀፍ ላይ፣ {hatched} ተፈልፍለዋል፣ {failed} አልተሳካም።",
        "hi": "अंडे: {pending} इनक्यूबेट हो रहे हैं, {hatched} फूटे, {failed} विफल हुए।",
    },
    "feed_location": {
        "ar": "مخزون العلف تلقاه بشاشة \"الأعلاف\" من القائمة الرئيسية (/feed/items)، أو من شاشة \"متابعة مبسّطة\" ← المخزون ← الأعلاف لو تبي عرض مبسّط بخط كبير.",
        "en": "You'll find feed stock on the \"Feed\" screen from the main menu (/feed/items), or under \"Simplified View\" → Stock → Feed for a large-text simplified display.",
        "am": "የመኖ ክምችት በዋናው ምናሌ ውስጥ በ«መኖ» ማያ ገጽ (/feed/items) ወይም በ«ቀላል እይታ» ← ክምችት ← መኖ ስር በትልቅ ፊደል ቀላል እይታ ያገኛሉ።",
        "hi": "चारे का स्टॉक आपको मुख्य मेनू से \"चारा\" स्क्रीन (/feed/items) पर मिलेगा, या \"सरलीकृत दृश्य\" ← स्टॉक ← चारा में बड़े अक्षरों वाला सरल दृश्य।",
    },
    "feed_cost_none": {
        "ar": "ما فيه خطط تغذية فعّالة حالياً بشاشة العلف، فما أقدر أحسب التكلفة اليومية.",
        "en": "There are no active feeding plans right now on the feed screen, so I can't calculate the daily cost.",
        "am": "አሁን በመኖ ማያ ገጽ ላይ ንቁ የመመገቢያ እቅድ የለም፣ ስለዚህ የዕለታዊ ወጪውን ማስላት አልችልም።",
        "hi": "चारा स्क्रीन पर अभी कोई सक्रिय आहार योजना नहीं है, इसलिए मैं दैनिक लागत की गणना नहीं कर सकता।",
    },
    "feed_cost_total": {
        "ar": "التكلفة اليومية التقديرية للعلف: {daily} (تقدير شهري ≈ {monthly}).",
        "en": "Estimated daily feed cost: {daily} (monthly estimate ≈ {monthly}).",
        "am": "የተገመተ ዕለታዊ የመኖ ወጪ: {daily} (ወርሃዊ ግምት ≈ {monthly})።",
        "hi": "अनुमानित दैनिक चारा लागत: {daily} (मासिक अनुमान ≈ {monthly})।",
    },
    "feed_cost_barn_line": {
        "ar": "- {barn} ({count} رأس، وصفة {ration}): {cost}",
        "en": "- {barn} ({count} head, ration {ration}): {cost}",
        "am": "- {barn} ({count} ራስ፣ ውህድ {ration}): {cost}",
        "hi": "- {barn} ({count} सिर, राशन {ration}): {cost}",
    },
    "alerts_none": {
        "ar": "ما فيه تنبيهات حالياً — كل شي تمام.",
        "en": "No alerts right now — everything's fine.",
        "am": "አሁን ምንም ማንቂያ የለም — ሁሉም ነገር ደህና ነው።",
        "hi": "अभी कोई अलर्ट नहीं है — सब कुछ ठीक है।",
    },
    "alerts_count": {
        "ar": "عندك {total} تنبيه ({urgent} عاجل). أهمها:",
        "en": "You have {total} alert(s) ({urgent} urgent). Top ones:",
        "am": "{total} ማንቂያ አለዎት ({urgent} አስቸኳይ)። ዋና ዋናዎቹ:",
        "hi": "आपके पास {total} अलर्ट हैं ({urgent} अत्यावश्यक)। मुख्य:",
    },
    "alerts_footer": {
        "ar": "افتح شاشة التنبيهات لعرض القائمة كاملة.",
        "en": "Open the Alerts screen to see the full list.",
        "am": "ሙሉ ዝርዝሩን ለማየት የማንቂያ ማያ ገጽን ይክፈቱ።",
        "hi": "पूरी सूची देखने के लिए अलर्ट स्क्रीन खोलें।",
    },
    "today_no_tasks": {
        "ar": "ما عندك مهام مفتوحة اليوم.",
        "en": "You have no open tasks today.",
        "am": "ዛሬ ምንም ክፍት ተግባር የለዎትም።",
        "hi": "आज आपके पास कोई खुला कार्य नहीं है।",
    },
    "today_tasks_header": {
        "ar": "📋 عندك {count} مهمة مفتوحة:",
        "en": "📋 You have {count} open task(s):",
        "am": "📋 {count} ክፍት ተግባር(ት) አለዎት:",
        "hi": "📋 आपके पास {count} खुला कार्य है:",
    },
    "today_urgent_header": {
        "ar": "\n⚠️ عندك {urgent} تنبيه عاجل من أصل {total}:",
        "en": "\n⚠️ You have {urgent} urgent alert(s) out of {total}:",
        "am": "\n⚠️ ከ{total} ውስጥ {urgent} አስቸኳይ ማንቂያ(ዎች) አለዎት:",
        "hi": "\n⚠️ कुल {total} में से आपके पास {urgent} अत्यावश्यक अलर्ट हैं:",
    },
    "today_nonurgent_note": {
        "ar": "\nℹ️ عندك {total} تنبيه غير عاجل — راجعها بشاشة التنبيهات وقت مناسب.",
        "en": "\nℹ️ You have {total} non-urgent alert(s) — review them on the Alerts screen when convenient.",
        "am": "\nℹ️ {total} አስቸኳይ ያልሆነ ማንቂያ(ዎች) አለዎት — ጊዜ ሲያገኙ በማንቂያ ማያ ገጽ ይገምግሙ።",
        "hi": "\nℹ️ आपके पास {total} गैर-अत्यावश्यक अलर्ट हैं — सुविधाजनक समय पर अलर्ट स्क्रीन पर देखें।",
    },
    "tasks_none": {
        "ar": "ما عندك مهام مفتوحة حالياً.",
        "en": "You have no open tasks right now.",
        "am": "አሁን ምንም ክፍት ተግባር የለዎትም።",
        "hi": "फिलहाल आपके पास कोई खुला कार्य नहीं है।",
    },
    "tasks_count": {
        "ar": "عندك {count} مهمة مفتوحة:",
        "en": "You have {count} open task(s):",
        "am": "{count} ክፍት ተግባር(ት) አለዎት:",
        "hi": "आपके पास {count} खुला कार्य है:",
    },
    "task_due": {
        "ar": " (موعدها {due})",
        "en": " (due {due})",
        "am": " (የሚጠበቅበት ቀን {due})",
        "hi": " (नियत {due})",
    },
    "task_locked": {
        "ar": " 🔒 مقفلة",
        "en": " 🔒 locked",
        "am": " 🔒 ተቆልፏል",
        "hi": " 🔒 लॉक",
    },
    "diseases_none": {
        "ar": "ما فيه أمراض مفتوحة حالياً — الوضع الصحي للقطيع سليم.",
        "en": "No open disease cases right now — the herd's health status is good.",
        "am": "አሁን ምንም ክፍት የበሽታ ጉዳይ የለም — የመንጋው ጤና ደህና ነው።",
        "hi": "फिलहाल कोई खुला रोग मामला नहीं है — झुंड की स्वास्थ्य स्थिति अच्छी है।",
    },
    "diseases_count": {
        "ar": "عندك {count} حالة مرض مفتوحة:",
        "en": "You have {count} open disease case(s):",
        "am": "{count} ክፍት የበሽታ ጉዳይ(ዮች) አሉዎት:",
        "hi": "आपके पास {count} खुला रोग मामला है:",
    },
    "disease_line": {
        "ar": "- {animal}: {name} (مفتوح منذ {days} يوم)",
        "en": "- {animal}: {name} (open for {days} days)",
        "am": "- {animal}: {name} (ለ{days} ቀናት ክፍት)",
        "hi": "- {animal}: {name} ({days} दिनों से खुला)",
    },
    "vaccinations_none": {
        "ar": "ما فيه تحصينات مستحقة أو متأخرة حالياً.",
        "en": "No vaccinations due or overdue right now.",
        "am": "አሁን የደረሰ ወይም የዘገየ ክትባት የለም።",
        "hi": "फिलहाल कोई टीकाकरण देय या विलंबित नहीं है।",
    },
    "vaccinations_count": {
        "ar": "عندك {count} تحصين مستحق/متأخر ({overdue} متأخر فعلياً):",
        "en": "You have {count} due/overdue vaccination(s) ({overdue} actually overdue):",
        "am": "{count} የደረሰ/የዘገየ ክትባት(ቶች) አለዎት ({overdue} በእርግጥ ዘግይተዋል):",
        "hi": "आपके पास {count} देय/विलंबित टीकाकरण हैं ({overdue} वास्तव में विलंबित):",
    },
    "vaccination_line": {
        "ar": "- {label} — {detail}",
        "en": "- {label} — {detail}",
        "am": "- {label} — {detail}",
        "hi": "- {label} — {detail}",
    },
    "finance_header": {
        "ar": "ملخص المالية لشهر {month}:",
        "en": "Finance summary for {month}:",
        "am": "የ{month} የፋይናንስ ማጠቃለያ:",
        "hi": "{month} के लिए वित्त सारांश:",
    },
    "finance_line": {
        "ar": "مبيعات: {sales} | مشتريات: {purchases} | مصروفات: {expenses}",
        "en": "Sales: {sales} | Purchases: {purchases} | Expenses: {expenses}",
        "am": "ሽያጭ: {sales} | ግዢ: {purchases} | ወጪ: {expenses}",
        "hi": "बिक्री: {sales} | खरीद: {purchases} | व्यय: {expenses}",
    },
    "finance_net": {
        "ar": "الصافي (بدون الديون): {net}",
        "en": "Net (excluding debt): {net}",
        "am": "ተጣራ (ያለ ዕዳ): {net}",
        "hi": "शुद्ध (ऋण को छोड़कर): {net}",
    },
    "finance_net_percent": {
        "ar": " — نسبة الربح: {percent}%",
        "en": " — profit percentage: {percent}%",
        "am": " — የትርፍ መቶኛ: {percent}%",
        "hi": " — लाभ प्रतिशत: {percent}%",
    },
    # بند إضافي 306 — فجوة حقيقية: `answer_with_image` (بند 305) كانت
    # تحسب `lang` بدون ما تستخدمه فعلياً — رسالة ثابتة عربية دائماً،
    # عكس مبدأ هذا الملف نفسه (بند 275).
    "vision_unavailable": {
        "ar": "تحليل الصور يحتاج تفعيل GEMINI_API_KEY حالياً — رفعت صورتك بنجاح، بس ما قدرت أحلّلها. جرّب بعد شوي أو اسأل نصياً.",
        "en": "Image analysis needs GEMINI_API_KEY to be enabled right now — your image was uploaded successfully, but I couldn't analyze it. Try again shortly or ask in text.",
        "am": "የምስል ትንተና አሁን የነቃ GEMINI_API_KEY ያስፈልገዋል — ምስልዎ በተሳካ ሁኔታ ተጭኗል፣ ግን መተንተን አልቻልኩም። ትንሽ ቆይተው ይሞክሩ ወይም በጽሑፍ ይጠይቁ።",
        "hi": "छवि विश्लेषण के लिए अभी GEMINI_API_KEY सक्रिय होना ज़रूरी है — आपकी छवि सफलतापूर्वक अपलोड हो गई, पर मैं उसका विश्लेषण नहीं कर सका। थोड़ी देर बाद कोशिश करें या टेक्स्ट में पूछें।",
    },
    "finance_debt": {
        "ar": "دين مستحق حالياً: {debt}",
        "en": "Currently outstanding debt: {debt}",
        "am": "አሁን ያለ ያልተከፈለ ዕዳ: {debt}",
        "hi": "वर्तमान बकाया ऋण: {debt}",
    },
}


def tr(key: str, lang: str, **kwargs) -> str:
    entry = T.get(key, {})
    template = entry.get(lang) or entry.get("ar", "")
    return template.format(**kwargs) if kwargs else template
