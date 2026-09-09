"""
قاعدة المعرفة البيطرية/التشغيلية للمساعد الذكي (بند 25، البند الثالث
بالمواصفة: "إرشادات تشغيلية وطبية متخصصة").

**قاعدة مُحترمة صراحة هنا** (نفس القاعدة المطبّقة بكل النظام — راجع
`app/health/`، `app/feed/feed_service.py`): "المساعد قرار مو طبيب" — كل
نص هنا إرشاد عام تشغيلي، بدون أي حساب جرعة دواء أو تشخيص حالة حيوان
معيّن. أي قرار علاجي أو جرعة نهائي **لازم يمر على الطبيب**.

كل بند معرفة له `keywords` (كلمات مفتاحية عربية للمطابقة) — `search()`
يرجّع أفضل تطابق حسب عدد الكلمات المشتركة مع سؤال المستخدم.
"""
from dataclasses import dataclass, field
from app.assistant.text_utils import normalize


@dataclass
class KBEntry:
    code: str
    title: str
    keywords: list[str]
    body: str
    normalized_keywords: list[str] = field(default_factory=list, repr=False)
    # بند إضافي 275 — طلبك الصريح "كل شي دفعة وحدة" لدعم لغات متعددة.
    # {lang: {"title": ..., "body": ...}} — لغة غير موجودة هنا = رجوع
    # تلقائي للعربي (تغطية تدريجية، صفر كسر لأي بند لسا ما تُرجم).
    translations: dict[str, dict[str, str]] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        self.normalized_keywords = [normalize(kw) for kw in self.keywords]


def localized_entry(entry: "KBEntry", lang: str) -> tuple[str, str]:
    """يرجع (title, body) بلغة `lang` لو مترجمة، وإلا العربي الأصلي."""
    tr = entry.translations.get(lang)
    if tr:
        return tr.get("title", entry.title), tr.get("body", entry.body)
    return entry.title, entry.body


ENTRIES: list[KBEntry] = [
    KBEntry(
        code="ostrich_hatching",
        title="إدارة التفقيس والحضانة (بيض النعام)",
        keywords=["تفقيس", "حاضنة", "حاضنات", "حضانة", "بيض", "بيضة", "فقس", "فقست", "نعام"],
        body=(
            "إرشادات عامة لإدارة التفقيس:\n"
            "• اجمع البيض من العشّ أول بأول (2-3 مرات باليوم) لتقليل تلوّثه أو كسره.\n"
            "• سجّل كل بيضة برقم مستقل فور جمعها (نفس مبدأ النظام: بيضة واحدة = سجل واحد) قبل ما تدخلها الحاضنة.\n"
            "• افحص جودة القشرة قبل الإدخال (نظافة، عدم وجود شروخ) وسجّل الوزن لو عندك ميزان — يساعد على متابعة فقدان الوزن الطبيعي أثناء الحضانة.\n"
            "• درجة الحرارة والرطوبة داخل الحاضنة يحددها نوع جهاز الحاضنة نفسه حسب دليل الشركة المصنّعة — النظام هنا ما يخزّن قيم حرارة/رطوبة، بس يتابع تاريخ الإدخال وتاريخ الفقس المتوقع تلقائياً من إعداد 'مدة حضانة بيض النعام' بشاشة الإعدادات.\n"
            "• لو فشلت بيضة، سجّل السبب بدقة (غير مخصّبة، توقّف نمو، مشكلة فقس) — يساعدك مع الوقت تكتشف نمط (حاضنة معيّنة، أم معيّنة...).\n"
            "• راجع طبيبك لو لاحظت نسبة فشل مرتفعة متكررة — قد يكون سببها تغذية الأمهات، مو الحاضنة."
        ),
        translations={
            "en": {
                "title": "Hatching & incubation management (ostrich eggs)",
                "body": (
                    "General hatching guidance:\n"
                    "• Collect eggs from the nest promptly (2-3 times a day) to reduce contamination or breakage.\n"
                    "• Log each egg with its own number as soon as you collect it (same principle as the rest of the system: one egg = one record) before placing it in the incubator.\n"
                    "• Check shell quality before loading it (cleanliness, no cracks) and record its weight if you have a scale — helps track normal weight loss during incubation.\n"
                    "• The incubator's temperature and humidity are set per the manufacturer's manual for that device — the system doesn't store temperature/humidity values, only tracks the loading date and expected hatch date automatically from the 'ostrich egg incubation duration' setting.\n"
                    "• If an egg fails, record the reason precisely (infertile, growth stopped, hatching problem) — over time this helps you spot a pattern (a specific incubator, a specific mother...).\n"
                    "• See your vet if you notice a recurring high failure rate — it may be caused by the mothers' nutrition rather than the incubator."
                ),
            },
        },
    ),
    KBEntry(
        code="ostrich_chick_care",
        title="رعاية فراخ النعام حديثة الفقس",
        keywords=["فرخ", "فراخ", "مولود نعام", "فرخ نعام", "رعاية فراخ"],
        body=(
            "إرشادات عامة لأول أسابيع الفرخ:\n"
            "• راقب وقوف الفرخ ومشيه أول 24-48 ساعة — أي تعثّر واضح بالمشي يحتاج فحص طبيب سريع.\n"
            "• وزن الفرخ بانتظام (النظام يسجّله بنفس شاشة تفاصيل الرأس مثل باقي الحيوانات) أفضل مؤشر مبكر لو فيه مشكلة تغذية أو صحة.\n"
            "• أبقِ الفرخ بمكان دافئ ونظيف بعيد عن الرطوبة الزائدة أول فترة.\n"
            "• أي إسهال أو خمول أو رفض أكل مستمر أكثر من يوم = استدعاء الطبيب، مو انتظار."
        ),
        translations={
            "en": {
                "title": "Care for newly hatched ostrich chicks",
                "body": (
                    "General guidance for the chick's first weeks:\n"
                    "• Watch the chick's standing and walking in the first 24-48 hours — any clear stumbling needs a quick vet check.\n"
                    "• Weigh the chick regularly (the system logs it on the same animal detail screen as any other animal) — the best early indicator of a feeding or health problem.\n"
                    "• Keep the chick somewhere warm, clean, and away from excess humidity early on.\n"
                    "• Any diarrhea, lethargy, or refusal to eat for more than a day means calling the vet, not waiting."
                ),
            },
        },
    ),
    KBEntry(
        code="vaccination_protocol",
        title="التحصينات — الجدول والمبادئ العامة",
        keywords=[
            "تحصين", "تحصينات", "تطعيم", "تطعيمات", "لقاح", "لقاحات",
            "هل النظام يقترح", "يقترح تطعيمات", "التاريخ المخطط", "رؤوس محددة للتحصين",
        ],
        body=(
            "مبادئ عامة (الجدول الفعلي لكل حيوان يحدده الطبيب حسب نوع اللقاح ووضع القطيع):\n"
            "• سجّل كل تحصين بتاريخه واسم اللقاح — النظام يحسب تلقائياً موعد التحصين القادم (`next_due_date`) ويظهره بشاشة التنبيهات قبل موعده بالمدة المحددة بالإعدادات.\n"
            "• تحصين الأم بعد الولادة له موعد منفصل (افتراضي 45 يوم بعد الولادة، قابل للتعديل من الإعدادات) — يظهر تلقائياً كمهمة عند دخول الحيوان مسار العزل بعد الولادة.\n"
            "• لا تُحصّن حيوان مريض حالياً (مرض مفتوح غير مُغلق) إلا بموافقة الطبيب صراحة — التحصين يزيد الحمل على جهاز مناعة ضعيف.\n"
            "• احترم فترة السحب (`withdrawal_until`) لأي لقاح له فترة سحب قبل البيع — النظام يمنع/ينبّه تلقائياً لو حاولت تبيع بهذي الفترة.\n"
            "• اختيار نوع اللقاح والجرعة قرار الطبيب حصراً — المساعد هنا ما يقترح جرعة.\n"
            "**هل النظام يقترح تطعيمات؟** النظام نفسه ما يحسب أو يقترح جرعة أو موعد تلقائي حسب عمر/نوع الحيوان — بس "
            "**يذكّرك** بموعد التحصين *القادم* بعد ما تسجّل تحصيناً فعلياً وتحدد له `next_due_date` بنفسك. لكن بالصيدلية "
            "(بند إضافي 290) فيه 3 أصناف لقاحات مرجعية جاهزة بالكتالوج (CDT، PPR+جدري مشترك، الحمى القلاعية) — أسماء "
            "ومدة حماية موثّقة من مصادر بيطرية حقيقية بس بدون جرعة ولا سعر (تعبيها أنت/الطبيب لما تستقبل المنتج الفعلي) — "
            "راجع بند المعرفة 'جدول تحصين الأغنام/الماعز المرجعي' للتفاصيل الكاملة.\n"
            "**'التاريخ المخطَّط' بشاشة 'جدولة تحصين جديد':** تاريخ مستقبلي تنوي تسوي فيه التحصين لاحقاً — تذكير/تخطيط بس، "
            "مو تسجيل تحصين فعلي وقتها. اختر حظيرة فيظهر لك أرقام رؤوسها الفعليين — علّم بس اللي يحتاج هذا اللقاح تحديداً "
            "(زر 'الكل' لو تقصدهم كلهم)، وسيب القائمة فاضية لو تقصد 'كل رؤوس الحظيرة' مهما تغيّرت لاحقاً."
        ),
        translations={
            "en": {
                "title": "Vaccinations — schedule and general principles",
                "body": (
                    "General principles (the actual schedule for each animal is set by the vet based on vaccine type and herd condition):\n"
                    "• Log every vaccination with its date and vaccine name — the system automatically computes the next due date and shows it on the alerts screen ahead of time, per your settings.\n"
                    "• The mother's post-partum vaccination has a separate due date (default 45 days after birth, adjustable in settings) — it appears automatically as a task once the animal enters the post-birth isolation path.\n"
                    "• Don't vaccinate a currently sick animal (an open, unclosed disease) without the vet's explicit approval — vaccination adds load to a weakened immune system.\n"
                    "• Respect the withdrawal period for any vaccine that has one before a sale — the system blocks/warns automatically if you try to sell during that period.\n"
                    "• Choosing the vaccine type and dose is the vet's decision alone — the assistant here never suggests a dose.\n"
                    "**Does the system suggest vaccinations?** The system itself doesn't compute or suggest an automatic dose or date based on the animal's age/type — it only **reminds** you of the *next* due date after you actually log a vaccination and set its next due date yourself. However, the pharmacy catalog has 3 ready reference vaccine entries (CDT, PPR+sheep pox combined, FMD) with names and protection durations documented from real veterinary sources, but without dose or price (you/the vet fill those in when you receive the actual product) — see the 'Reference sheep/goat vaccination schedule' knowledge entry for full details.\n"
                    "**The 'planned date' on the 'schedule new vaccination' screen:** a future date you intend to do the vaccination on later — a reminder/plan only, not an actual vaccination record at that time. Pick a barn and its actual head numbers appear — check only the ones that need this specific vaccine ('all' button if you mean all of them), and leave the list empty if you mean 'the whole barn's heads' whoever they turn out to be later."
                ),
            },
        },
    ),
    KBEntry(
        code="isolation_protocol",
        title="العزل التلقائي (الحجر الصحي) بالنظام",
        keywords=["عزل", "حجر", "حجر صحي", "الحظيرة عزل", "حظيرة العزل", "بعد ولادة المولود", "وش يصير للمولود بعد الولادة"],
        body=(
            "كيف يشتغل العزل التلقائي بالنظام حالياً:\n"
            "• أي ولادة جديدة تنقل الأم والمولود تلقائياً لأول حظيرة من نوع 'عزل'، وتُفتح 7 مهام فحص يومي + مهمة فحص طبيب خلال أول 48 ساعة + مهمة وزن + مهمتي تحصين (أم ومولود).\n"
            "• الحيوان الوافد جديد (شراء أو هدية) يمر بفترة حجر (افتراضي 21 يوم، قابلة للتعديل من الإعدادات) قبل ما يُعتبر جزء طبيعي من القطيع — الرصيد الافتتاحي (حيوان كان موجود أصلاً) مستثنى من هذا الحجر.\n"
            "• الخروج من العزل يحتاج فعلياً: فحص بيطري موثّق + تحصين المولود، وتحصين الأم مرتبط بتاريخ آخر ولادة لها — البوابة ما تفتح تلقائياً لمجرد مرور الوقت.\n"
            "• أي علامة غير طبيعية أثناء فترة العزل (خمول، إسهال، رفض رضاعة) = استدعاء الطبيب فوراً بدل انتظار الفحص اليومي المجدول."
        ),
        translations={
            "en": {
                "title": "Automatic isolation (quarantine) in the system",
                "body": (
                    "How automatic isolation currently works in the system:\n"
                    "• Any new birth automatically moves the mother and newborn to the first barn of type 'isolation', and opens 7 daily check tasks + a vet exam task within the first 48 hours + a weighing task + two vaccination tasks (mother and newborn).\n"
                    "• A newly arriving animal (purchase or gift) goes through a quarantine period (default 21 days, adjustable in settings) before being considered a normal part of the herd — an opening-balance animal (already in the herd) is exempt from this quarantine.\n"
                    "• Exiting isolation actually requires: a documented vet exam + newborn vaccination, and the mother's vaccination tied to her last birth date — the gate doesn't open automatically just because time has passed.\n"
                    "• Any abnormal sign during isolation (lethargy, diarrhea, refusing to nurse) means calling the vet immediately instead of waiting for the scheduled daily check."
                ),
            },
        },
    ),
    KBEntry(
        code="sprouted_barley",
        title="الشعير المستنبت (العلف الأخضر)",
        keywords=["شعير مستنبت", "الشعير المستنبت", "علف اخضر", "علف أخضر", "استنبات"],
        body=(
            "الشعير المستنبت (Fodder) كمكوّن علف مكمّل:\n"
            "• يُنبَّت الشعير عادة خلال 6-8 أيام (نقع + ري متكرر بدون تربة) ويعطي كتلة خضراء طازجة عالية الرطوبة.\n"
            "• يستخدم كمكمّل غذائي طازج (مصدر فيتامينات وألياف قابلة للهضم بسهولة)، مو بديل كامل عن العليقة المركزة — لازم يُدخل ضمن وصفة متوازنة.\n"
            "• سجّله بالنظام كمكوّن علف منفصل (`Feed`) بقيمه الغذائية التقريبية (بروتين/طاقة) عشان حاسبة الوصفات تحسبه صح ضمن أي تركيبة تضيفه لها.\n"
            "• راقب رطوبته العالية — يفسد بسرعة لو تخزّن، فالأفضل يُنتَج ويُستهلك يومياً بكمية محسوبة، مو يُخزَّن لفترة طويلة."
        ),
        translations={
            "en": {
                "title": "Sprouted barley (green fodder)",
                "body": (
                    "Sprouted barley (fodder) as a supplementary feed component:\n"
                    "• Barley is usually sprouted over 6-8 days (soaking + repeated watering, no soil) and yields a fresh, high-moisture green mass.\n"
                    "• Used as a fresh supplement (a source of vitamins and easily digestible fiber), not a full replacement for concentrate feed — it must be part of a balanced ration.\n"
                    "• Log it in the system as a separate feed component (`Feed`) with its approximate nutritional values (protein/energy) so the ration calculator accounts for it correctly in any mix you add it to.\n"
                    "• Watch its high moisture — it spoils quickly if stored, so it's best produced and consumed daily in a calculated amount rather than stored for long."
                ),
            },
        },
    ),
    KBEntry(
        code="azolla",
        title="الأزولا كعلف بديل غني بالبروتين",
        keywords=["ازولا", "الأزولا", "أزولا", "azolla"],
        body=(
            "الأزولا (نبات مائي) كمصدر بروتين بديل/مكمّل:\n"
            "• نسبة بروتين خام مرتفعة نسبياً مقارنة بأغلب الأعلاف الخضراء التقليدية، وتُستزرع بأحواض مائية ضحلة بمعدل نمو سريع.\n"
            "• تُقدَّم طازجة أو مجفّفة ضمن الوصفة كمصدر بروتين إضافي، وليست بديلاً كاملاً عن مصادر البروتين الرئيسية بالعليقة — تُدخل بنسبة مدروسة ضمن التركيبة.\n"
            "• قبل اعتمادها بكمية كبيرة بوصفة دائمة، سجّل قيمها الغذائية الفعلية بالنظام (`Feed`) من تحليل مخبري أو مرجع موثوق لو متوفر، بدل تقدير عام — يخلي حساب الوصفة والتكلفة دقيق.\n"
            "• تحتاج مصدر مياه نظيف ومستقر لاستزراعها — جودة المياه تؤثر مباشرة على جودة المحصول."
        ),
        translations={
            "en": {
                "title": "Azolla as a protein-rich alternative feed",
                "body": (
                    "Azolla (an aquatic plant) as an alternative/supplementary protein source:\n"
                    "• Relatively high crude protein compared to most traditional green feeds, grown in shallow water ponds with a fast growth rate.\n"
                    "• Fed fresh or dried as part of the ration, as an extra protein source — not a full replacement for the ration's main protein sources; include it at a measured proportion.\n"
                    "• Before relying on a large amount in a permanent ration, log its actual nutritional values in the system (`Feed`) from a lab analysis or a reliable reference if available, instead of a rough estimate — keeps the ration and cost calculations accurate.\n"
                    "• Needs a clean, stable water source to grow — water quality directly affects the crop's quality."
                ),
            },
        },
    ),
    KBEntry(
        code="feed_ration_basics",
        title="أساسيات جدول العليقة والتوازن الغذائي",
        keywords=["عليقة", "وصفة علف", "توازن غذائي", "جدول تغذية", "خطة تغذية"],
        body=(
            "أساسيات بناء وصفة متوازنة (بدون إعادة اختراع حاسبة العلف الموجودة أصلاً بالنظام):\n"
            "• استخدم شاشة 'حاسبة العلف' — تحسب الاحتياج اليومي تلقائياً من وزن الحيوان الفعلي وحالته الفسيولوجية (نمو/حمل متأخر/رضاعة/صيانة) المخمّنة من دورة الإنتاج.\n"
            "• الأرقام المستخدمة تقديرات عامة للمجترات الصغيرة (غنم/ماعز)، مو توصية بيطرية معتمدة لمزرعتك تحديداً — راجعها مع طبيبك قبل قرارات شراء كبيرة.\n"
            "• الوصفة تُبنى من مكوّنات مسجّلة بنسب مئوية من إجمالي الوزن — النظام يحسب البروتين/الطاقة الموزونة وتكلفة الكيلو تلقائياً من قيم كل مكوّن.\n"
            "• لو المخزون الحالي ما يكفي وصفة معيّنة، الحاسبة تنبّهك وترشّح بديل من المتوفر فعلياً — راجع 'ترشيح الوصفة' بدل التركيب اليدوي."
        ),
        translations={
            "en": {
                "title": "Basics of ration planning and nutritional balance",
                "body": (
                    "Basics of building a balanced ration (without reinventing the feed calculator already built into the system):\n"
                    "• Use the 'feed calculator' screen — it automatically computes the daily requirement from the animal's actual weight and its physiological state (growth/late pregnancy/lactation/maintenance) inferred from the production cycle.\n"
                    "• The figures used are general estimates for small ruminants (sheep/goats), not a veterinary recommendation certified for your specific farm — review them with your vet before major purchase decisions.\n"
                    "• A ration is built from logged components as percentages of total weight — the system automatically computes weighted protein/energy and cost per kilo from each component's values.\n"
                    "• If current stock isn't enough for a given ration, the calculator warns you and suggests an alternative from what's actually available — see 'ration substitution' instead of manual mixing."
                ),
            },
        },
    ),
    KBEntry(
        code="general_health_red_flags",
        title="علامات تستدعي استدعاء الطبيب فوراً",
        keywords=["اعراض", "أعراض", "خمول", "مريض", "مرض", "استدعاء طبيب", "علامات خطر"],
        body=(
            "هذي علامات عامة تستدعي **استدعاء الطبيب فوراً**، مو انتظار الجولة العادية — المساعد هنا ما يشخّص ولا يقترح علاج:\n"
            "• رفض أكل أو شرب كامل لأكثر من يوم.\n"
            "• إسهال شديد أو مستمر، خصوصاً بمولود أو فرخ حديث.\n"
            "• صعوبة تنفّس واضحة أو سعال متكرر.\n"
            "• عرج مفاجئ أو رفض الوقوف تماماً.\n"
            "• حرارة جسم مرتفعة محسوسة مع خمول واضح.\n"
            "• أي نزيف أو تورّم غير طبيعي.\n"
            "سجّل الحالة بشاشة 'الأمراض' أو ارفع بلاغ من شاشة البلاغات فور ملاحظتها — التشخيص والعلاج والجرعة قرار الطبيب حصراً."
        ),
        translations={
            "en": {
                "title": "Signs that call for the vet immediately",
                "body": (
                    "These are general signs that call for **calling the vet immediately**, not waiting for the regular round — the assistant here doesn't diagnose or suggest treatment:\n"
                    "• Complete refusal to eat or drink for more than a day.\n"
                    "• Severe or persistent diarrhea, especially in a newborn or chick.\n"
                    "• Clear difficulty breathing or repeated coughing.\n"
                    "• Sudden limping or complete refusal to stand.\n"
                    "• A noticeably high body temperature combined with clear lethargy.\n"
                    "• Any abnormal bleeding or swelling.\n"
                    "Log the case on the 'diseases' screen or file a report from the reports screen as soon as you notice it — diagnosis, treatment, and dosage are the vet's decision alone."
                ),
            },
        },
    ),
    # خمسة بنود جديدة (بند إضافي 55.3) — فكرة التوسيع أساسها كود "مقاني"
    # (دليل مربٍّ موسّع)، لكن المحتوى مبني من الصفر ليطابق شاشات وميزات
    # نظامنا الفعلية بدل نسخ نصوص عامة، وبنفس قاعدة "المساعد قرار مو طبيب".
    KBEntry(
        code="howto_inventory_count",
        title="كيف أسوي جرد وأحسب الهالك؟",
        keywords=[
            "جرد", "كيف اسوي جرد", "جرد المستودع", "جرد المخزون", "حساب الهالك",
            "هالك العلف", "هالك الدواء", "هالك المعدات", "سجل الجرد", "نقص المخزون",
        ],
        body=(
            "من 'المستودعات' ← زر 'جرد' جنب أي صنف (علف/دواء/معدات): اكتب الكمية الفعلية اللي وزنتها/عددتها "
            "بالمستودع — النظام يقارنها برصيده المحسوب (من حركات الشراء/الصرف) ويصحّح المخزون تلقائياً.\n"
            "لو الفعلي أكثر من المحسوب (زيادة): تصحيح مخزون بس، بدون أي أثر مالي.\n"
            "لو الفعلي أقل (نقص): يُحتسب 'هالك' — مصروف مالي غير مباشر بقيمة (الكمية الناقصة × سعر الوحدة "
            "المسجَّل بالصنف)، يُوزَّع تلقائياً على كل الرؤوس النشطة بنفس تقرير تكلفة الرأس الشهرية (بند 18) — "
            "بدون ما تحسبها يدوياً.\n"
            "'المستودعات' ← 'سجل الجرد' يعرض كل عمليات الجرد السابقة بكل الأقسام بتاريخها وقيمة أي هالك."
        ),
        translations={
            "en": {
                "title": "How do I do a stock count and compute loss?",
                "body": (
                    "From 'Warehouses' → 'Count' button next to any item (feed/medicine/equipment): enter the actual quantity you weighed/counted "
                    "in the warehouse — the system compares it to its computed balance (from purchase/consumption movements) and corrects the stock automatically.\n"
                    "If actual is more than computed (surplus): a stock correction only, with no financial effect.\n"
                    "If actual is less (shortage): counted as 'loss' — an indirect expense worth (missing quantity × the item's logged unit price), "
                    "distributed automatically across all active heads via the same monthly per-head cost report — with no manual calculation from you.\n"
                    "'Warehouses' → 'Count log' shows every past count across all sections with its date and any loss value."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_stock_purchase",
        title="كيف أسجّل شراء علف أو معدات بضغطة وحدة؟",
        keywords=[
            "شراء علف", "شراء اعلاف", "شراء معدات", "زر شراء علف", "زر شراء معدات",
            "تسجيل شراء علف", "شراء ومالية معاً", "شراء يزيد المخزون",
            "شراء يسجل ماليه", "شراء يسجل مالية", "كم كيلو بالشراء",
            "اضافة مكون من فورم الشراء", "اضافة صنف من فورم الشراء",
        ],
        body=(
            "'العلف' ← 'مكوّنات العلف' ← زر 'شراء' (وبنفس الطريقة 'المعدات' ← زر 'شراء'): "
            "فورم واحد يسوي عمليتين مربوطتين بضغطة وحدة — يزيد المخزون فوراً (حركة 'وارد') "
            "**ويسجّل العملية المالية** (المبلغ = الكمية × سعر الوحدة، مع إرفاق فاتورة المورّد لو عندك) بنفس الوقت.\n"
            "بدل ما تدخل من 'حركة المخزون' لوحدها ثم 'المالية ← عملية جديدة' لوحدها — الاثنين يصيران سجلاً واحداً "
            "مترابطاً، ويحتاج صلاحية إدارة القسم (علف/معدات) وصلاحية المالية معاً لأنه ينشئ عملية مالية فعلية.\n"
            "لو الصنف اللي تشتريه مو مسجَّل أصلاً، زر 'إضافة مكون/صنف جديد' جنب قائمة الاختيار بنفس الفورم يفتح لك "
            "فورم الإضافة مباشرة بدون ما تطلع من صفحة الشراء. وتحت حقل الكمية يظهر تلقائياً 'الوحدة' الفعلية للصنف "
            "(كجم/كيس/ربطة...) مع إجمالي تقريبي بالكيلوجرام لو مسجَّل وزن الوحدة (بند 202) — عشان تعرف بالضبط كم "
            "كيلو انضاف فعلياً وقت تقسّمها لاحقاً على الحظائر أو الرؤوس."
        ),
        translations={
            "en": {
                "title": "How do I log a feed or equipment purchase in one click?",
                "body": (
                    "'Feed' → 'Feed components' → 'Purchase' button (and the same way 'Equipment' → 'Purchase'): "
                    "one form does two linked operations in one click — increases stock immediately (an 'in' movement) "
                    "and **logs the financial transaction** (amount = quantity × unit price, with a supplier invoice attached if you have one) at the same time.\n"
                    "Instead of entering it via 'stock movement' alone then 'finance → new transaction' separately — the two become one linked record, "
                    "and it needs both the section's management permission (feed/equipment) and the finance permission together since it creates a real financial transaction.\n"
                    "If the item you're buying isn't logged yet, the 'add new component/item' button next to the selection list on the same form opens the add "
                    "form directly without leaving the purchase page. Under the quantity field, the item's actual unit (kg/bag/bundle...) shows automatically "
                    "with an approximate kilogram total if the unit weight is logged — so you know exactly how many kilos were actually added when you split it "
                    "across barns or heads later."
                ),
            },
        },
    ),
    KBEntry(
        code="buying_checklist",
        title="فحص الحيوان قبل الشراء",
        keywords=["شراء", "شراء حيوان", "قبل الشراء", "فحص قبل الشراء", "شراء رأس", "شراء دفعة"],
        body=(
            "نقاط عامة يفحصها المربي قبل قرار الشراء (فحص طبي نهائي دائماً عند الطبيب):\n"
            "• العين والأنف والتنفس والأسنان والفك والأرجل — أي علامة غير طبيعية سؤال قبل الشراء لا بعده.\n"
            "• الضرع والحلمات للإناث، والخصيتان للفحول.\n"
            "• العمر التقريبي وتاريخ آخر تحصين/علاج لو متوفر من البائع.\n"
            "• سجّل الحيوان بالنظام فور الشراء (شراء فردي أو 'شراء دفعة' لعدة رؤوس دفعة واحدة) — يدخل تلقائياً فترة الحجر (افتراضي 21 يوم، قابلة للتعديل من الإعدادات) قبل ما يُخلط بالقطيع.\n"
            "• لو الدفعة فيها رأس تشتبه فيها، استخدم 'استبعاد فردي' بمسار استقبال الدفعة — تبقى بمرحلتها لحالها بينما تكمل بقية الدفعة السليمة."
        ),
        translations={
            "en": {
                "title": "Checking an animal before buying",
                "body": (
                    "General points a breeder checks before deciding to buy (the final medical exam is always with the vet):\n"
                    "• Eyes, nose, breathing, teeth, jaw, and legs — any abnormal sign is a question before the purchase, not after.\n"
                    "• Udder and teats for females, and testicles for males.\n"
                    "• Approximate age and the date of the last vaccination/treatment if the seller has it.\n"
                    "• Log the animal in the system as soon as you buy it (single purchase or 'batch purchase' for several heads at once) — it automatically enters the quarantine period (default 21 days, adjustable in settings) before mixing with the herd.\n"
                    "• If a head in the batch looks suspicious, use 'individual exclusion' in the batch-receiving flow — it stays at its own stage while the rest of the healthy batch continues."
                ),
            },
        },
    ),
    KBEntry(
        code="biosecurity",
        title="الأمن الحيوي ومنع انتقال العدوى",
        keywords=["امن حيوي", "أمن حيوي", "منع العدوى", "تعقيم", "انتقال المرض", "عدوى"],
        body=(
            "مبادئ عامة لتقليل انتقال الأمراض داخل المزرعة (تكمل خطة العزل التلقائية بالنظام، ما تلغيها):\n"
            "• طهّر الأحذية والأدوات ووسيلة النقل قبل الدخول للحظائر، خصوصاً بعد زيارة مزرعة ثانية.\n"
            "• لا تشارك إبر الحقن أو أدوات العلاج بين حيوانات مختلفة.\n"
            "• اعتنِ بالحيوان السليم قبل المريض بجولتك اليومية، مو العكس — يقلل نقل العدوى بالملابس واليدين.\n"
            "• أي حيوان مجهول الحالة الصحية (وافد جديد، أو من سوق/معرض) يدخل حظيرة العزل أولاً — نفس منطق العزل التلقائي الموجود أصلاً بالنظام.\n"
            "• لاحظ تكرار نفوق أو مرض بنفس الحظيرة خلال فترة قصيرة — علامة تستدعي مراجعة الطبيب لفحص السبب البيئي، مو بس علاج كل حالة لحالها."
        ),
        translations={
            "en": {
                "title": "Biosecurity and preventing disease spread",
                "body": (
                    "General principles for reducing disease spread within the farm (complements the system's automatic isolation plan, doesn't replace it):\n"
                    "• Disinfect footwear, tools, and transport before entering the barns, especially after visiting another farm.\n"
                    "• Don't share injection needles or treatment tools between different animals.\n"
                    "• Attend to healthy animals before sick ones on your daily round, not the other way around — reduces disease transfer via clothes and hands.\n"
                    "• Any animal of unknown health status (a new arrival, or from a market/exhibition) goes into the isolation barn first — same logic as the automatic isolation already built into the system.\n"
                    "• Notice repeated deaths or disease in the same barn within a short period — a sign that calls for a vet review to check the environmental cause, not just treating each case on its own."
                ),
            },
        },
    ),
    KBEntry(
        code="heat_stress",
        title="إدارة الحرارة والإجهاد الحراري",
        keywords=["حرارة", "حر", "صيف", "اجهاد حراري", "إجهاد حراري", "طقس حار"],
        body=(
            "مبادئ عامة لتقليل أثر الحر (السعودية بيئة حارة معظم السنة):\n"
            "• وفّر ظلاً وتهوية جيدة، وتجنّب الزحام داخل الحظيرة وقت الذروة الحرارية.\n"
            "• زد عدد مرات فحص المشارب وتوفر الماء — الاحتياج يرتفع مع الحر وخصوصاً للحوامل والمرضعات.\n"
            "• أجّل أي إجراء مرهق (نقل، فرز، عمليات جماعية، نقل لحظيرة جديدة) للأوقات الأبرد من اليوم (فجراً/مساءً) قدر الإمكان.\n"
            "• راجع 'شاشة الطقس' بالنظام (لو موقع المزرعة مضبوط) لمتابعة درجة الحرارة الحالية والمتوقعة قبل جدولة أي عملية جماعية.\n"
            "• لهاث شديد مستمر أو ضعف مفاجئ وقت الحر الشديد = حالة طارئة تستدعي الطبيب فوراً، مو انتظار برودة الجو."
        ),
        translations={
            "en": {
                "title": "Managing heat and heat stress",
                "body": (
                    "General principles for reducing the effect of heat (Saudi Arabia is a hot environment most of the year):\n"
                    "• Provide shade and good ventilation, and avoid crowding inside the barn during peak heat hours.\n"
                    "• Check water troughs more often and ensure water availability — the requirement rises with heat, especially for pregnant and nursing females.\n"
                    "• Postpone any tiring procedure (transport, sorting, group operations, moving to a new barn) to the cooler times of day (early morning/evening) as much as possible.\n"
                    "• Check the system's 'weather screen' (if the farm's location is set) to track current and forecast temperature before scheduling any group operation.\n"
                    "• Persistent heavy panting or sudden weakness during severe heat is an emergency that calls for the vet immediately, not waiting for cooler weather."
                ),
            },
        },
    ),
    KBEntry(
        code="water_minerals",
        title="الماء والأملاح المعدنية",
        keywords=["ماء", "مياه", "املاح", "أملاح", "مشرب", "مشارب", "معادن"],
        body=(
            "مبادئ عامة لتوفير الماء والأملاح:\n"
            "• الماء النظيف المتجدد أهم من أي مكمّل غذائي — نظّف المشارب بانتظام وافحص جودة الماء لو لاحظت رفض شرب جماعي.\n"
            "• الاحتياج يرتفع مع الحر والحمل والرضاعة والتسمين — راقب استهلاك المشارب اليومي كمؤشر مبكر لمشاكل صحية أو بيئية.\n"
            "• استخدم أملاح ومعادن مخصَّصة للأغنام/الماعز تحديداً — خلطات حيوانات أخرى قد تحتوي نسب معادن غير مناسبة.\n"
            "• سجّل أي منتج أملاح كمكوّن علف (`Feed`) بالنظام لو تستخدمه ضمن وصفة ثابتة، عشان حاسبة العلف تحسبه صح."
        ),
        translations={
            "en": {
                "title": "Water and mineral salts",
                "body": (
                    "General principles for providing water and salts:\n"
                    "• Clean, refreshed water matters more than any nutritional supplement — clean the troughs regularly and check water quality if you notice a collective refusal to drink.\n"
                    "• The requirement rises with heat, pregnancy, lactation, and fattening — watch daily trough consumption as an early indicator of health or environmental problems.\n"
                    "• Use salts and minerals formulated specifically for sheep/goats — mixes for other animals may contain unsuitable mineral ratios.\n"
                    "• Log any salt product as a feed component (`Feed`) in the system if you use it within a fixed ration, so the feed calculator accounts for it correctly."
                ),
            },
        },
    ),
    KBEntry(
        code="smart_sale_explained",
        title="كيف يقترح النظام البيع أو الاستبعاد؟",
        keywords=["بيع ذكي", "لماذا البيع", "سبب البيع", "درجة البيع", "توصية بيع", "استبعاد"],
        body=(
            "شرح عام لمنطق شاشة 'البيع الذكي' الموجودة أصلاً بالنظام (`/animals/smart-sale`) — القرار النهائي دائماً للمربي:\n"
            "• للذكور: العمر هو العامل الأهم (بيع عادي بعد 6 أشهر تقريباً، الأضاحي تحتاج عمراً أعلى)، والوزن المتوقف أو المتراجع يرفع إلحاح البيع لأنه يستهلك علفاً بدون فائدة.\n"
            "• للإناث: أي علامة من أربع تعني بيع فوري — تأخر حمل واضح، عدم حمل إطلاقاً رغم بلوغها سن التقريع، رفض إرضاع مولودها، أو تلف الضرع (الأخيرتان تُسجَّلان يدوياً بصفحة الحيوان لأنهما ملاحظة فعلية).\n"
            "• الدرجة الرقمية (من 100) بالشاشة مصحوبة دائماً بتفسير نصي يوضح كل سبب ساهم فيها — راجعه قبل اتخاذ القرار، مو الرقم لحاله.\n"
            "• النافذة الزمنية المقترحة (7/14/30/60 يوم) تقدير إداري لتفادي تراكم التكلفة، مو موعداً إلزامياً."
        ),
        translations={
            "en": {
                "title": "How does the system suggest selling or culling?",
                "body": (
                    "General explanation of the 'smart sale' screen's logic already in the system (`/animals/smart-sale`) — the final decision is always the breeder's:\n"
                    "• For males: age is the most important factor (a normal sale after about 6 months, sacrificial animals need a higher age), and stalled or declining weight raises the sale urgency because it's consuming feed with no benefit.\n"
                    "• For females: any of four signs means an immediate sale — a clear delay in conception, no conception at all despite reaching breeding age, refusing to nurse her newborn, or udder damage (the last two are logged manually on the animal page since they're an actual observation).\n"
                    "• The numeric score (out of 100) on the screen always comes with a text explanation of every reason that contributed to it — review it before deciding, not the number alone.\n"
                    "• The suggested time window (7/14/30/60 days) is a management estimate to avoid cost buildup, not a mandatory deadline."
                ),
            },
        },
    ),

    # ---------- إرشاد استخدام التطبيق (بند إضافي 114) ----------
    # قبل هذا البند، قاعدة المعرفة كلها إرشادات بيطرية/تشغيلية عامة —
    # ما فيه أي إجابة تشرح "وين أضغط بالضبط" داخل التطبيق نفسه. هذي
    # المجموعة الجديدة تجاوب على أكثر 9 أسئلة "كيف أسوي كذا بالتطبيق"
    # للشاشات الأساسية، بنفس آلية المطابقة الموجودة أصلاً — صفر تغيير
    # بمنطق البحث نفسه.
    KBEntry(
        code="howto_market_trip",
        title="طلّعت حيوان للسوق وما بعت — كيف أتصرف؟",
        keywords=[
            "طلعتها للسوق", "طلعت للسوق", "طلع للسوق", "خروج للسوق", "ما بعت",
            "الغاء البيع", "إلغاء البيع", "رجع بدون بيع", "بدون بيع", "استرجاع البيع", "رجّعتها المزرعة",
        ],
        body=(
            "من صفحة 'دورة الإنتاج' لأي رأس نشط، بطاقة 'رحلة السوق': زر 'طلّعها للسوق' يسجّل خروجها "
            "كتذكير مرئي بس (ما يغيّر حالتها — تضل 'نشطة' بكل الشاشات الثانية زي التغذية والمهام).\n"
            "لو رجعت بدون بيع: نفس البطاقة فيها زر 'رجع للمزرعة بدون بيع' — يمسح التذكير، صفر أثر على أي سجل مالي "
            "لأنه ما فيه بيع اتسجّل أصلاً.\n"
            "لو بعتها فعلاً: سجّل البيع بفورم 'قرار الخروج' العادي (السعر، المشتري، الفاتورة) — يُمسح تذكير رحلة "
            "السوق تلقائياً وقتها.\n"
            "ولو سجّلت بيع فعلي وبعدين احتجت تتراجع عنه (صار بيع فعلي بالنظام مو مجرد رحلة سوق): زر 'استرجاع البيع' "
            "بنفس الصفحة (يظهر بعد تسجيل البيع) يرجّع الرأس نشط تلقائياً، والعملية المالية تُلغى (تبقى بالسجل للتدقيق، "
            "ما تُحذف نهائياً)."
        ),
        translations={
            "en": {
                "title": "I sent an animal to market and didn't sell — what do I do?",
                "body": (
                    "From the 'production cycle' page for any active head, the 'market trip' card: the 'send to market' button logs its departure "
                    "as a visual reminder only (doesn't change its status — it stays 'active' on every other screen like feeding and tasks).\n"
                    "If it comes back unsold: the same card has a 'return to farm without selling' button — clears the reminder, with zero effect on any "
                    "financial record since no sale was ever logged.\n"
                    "If you actually sold it: log the sale on the normal 'exit decision' form (price, buyer, invoice) — the market trip reminder is "
                    "cleared automatically at that point.\n"
                    "And if you logged an actual sale and later need to undo it (it became a real sale in the system, not just a market trip): the "
                    "'undo sale' button on the same page (appears after the sale is logged) returns the head to active automatically, and the financial "
                    "transaction is cancelled (kept in the record for audit, not permanently deleted)."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_add_animal",
        title="كيف أضيف رأس جديد؟",
        keywords=[
            "اضافة حيوان", "اضف حيوان", "تسجيل حيوان", "رأس جديد", "شريت راس", "اضافة راس", "كيف اضيف حيوان",
            "تسجيل مولود", "اسجل مولود", "كيف اسجل مولود", "اضافة مولود", "مولود جديد", "كيف اضيف مولود",
            "يتسجل المولود تلقائي", "المولود يتسجل تلقائي", "هل المولود يتسجل", "يسجل نفسه", "تسجيل تلقائي للمولود",
        ],
        body=(
            "من القائمة الجانبية ☰ اختر 'الحيوانات' ثم زر '+ حيوان جديد' (أو مباشرة رابط /animals/new):\n"
            "• حدد المصدر أول شي (شراء / مولود بالمزرعة / هدية / رصيد افتتاحي) — يحدد الحقول المطلوبة بعده.\n"
            "• الحظيرة واللون إلزاميان بكل الحالات.\n"
            "• لو المصدر 'شراء' وحطيته بحظيرة نوع 'عزل'، النظام يفتح تلقائياً مهمتي رش وقائي وتحصين مبدئي — بدون أي خطوة إضافية منك.\n"
            "• لو المصدر 'مولود' لازم تربطه بأمه — رقمه المؤقت يتولّد تلقائياً لو ما كتبت رقماً، وسجّل جنسه ووزنه وغرضه (تربية/تسمين/بيع) لأنها مطلوبة لأي رأس بغض النظر عن مصدره.\n"
            "• حقل 'السعر' اتركه فاضي للمولود — ما له سعر شراء أصلاً، تكلفته تُحسب تلقائياً من استهلاك العلف الفعلي عبر تقرير كفاءة العلف (FCR)، ما يحتاج أي إدخال يدوي منك."
        ),
        translations={
            "en": {
                "title": "How do I add a new head?",
                "body": (
                    "From the side menu ☰ pick 'Animals' then '+ New animal' (or the /animals/new link directly):\n"
                    "• Set the source first (purchase / born on farm / gift / opening balance) — determines the required fields after it.\n"
                    "• Barn and color are required in every case.\n"
                    "• If the source is 'purchase' and you put it in an 'isolation' type barn, the system automatically opens a preventive spray and initial vaccination task — no extra step from you.\n"
                    "• If the source is 'newborn' you must link it to its mother — a temporary number is generated automatically if you don't type one, and log its sex, weight, and purpose (breeding/fattening/sale) since these are required for any head regardless of source.\n"
                    "• Leave the 'price' field empty for a newborn — it never had a purchase price, its cost is computed automatically from actual feed consumption via the feed conversion (FCR) report, no manual entry needed."
                ),
            },
        },
    ),
    KBEntry(
        code="newborn_faq",
        title="رحلة المولود بالنظام — من التسجيل للفطام",
        keywords=[
            "هل المولود يتسجل تلقائي", "يسجل المولود نفسه", "متى افطم المولود", "متى أفطم المولود",
            "فطام المولود", "عمر الفطام", "وزن المولود", "تحصين المولود", "اول تحصين للمولود",
            "المولود له سعر", "تكلفة المولود", "كم عمر المولود",
        ],
        body=(
            "لا — التسجيل الأولي **يدوي** (زر '+ حيوان جديد'، مصدر 'مولود بالمزرعة'، مربوط بأمه) — النظام ما "
            "يكتشف الولادة لحاله. لكن بعد التسجيل، كل شي بعده أوتوماتيكي بالكامل:\n"
            "• ينتقل هو وأمه تلقائياً لأول حظيرة 'عزل'، وتُفتح 7 مهام فحص يومي + فحص طبيب خلال 48 ساعة + وزن + "
            "تحصين (راجع 'العزل التلقائي' للتفاصيل الكاملة).\n"
            "• ما له سعر شراء أصلاً (يترك فاضي) — تكلفته تُحسب تلقائياً من استهلاك العلف الفعلي (تقرير FCR).\n"
            "• الفطام: بوابة مرحلة 'الرضاعة والفطام' (مرحلة 8 بدورة الإنتاج) تحتاج عمر أدنى (افتراضي 60 يوم، "
            "قابل للتعديل من الإعدادات) — وإما تسجّل 'تاريخ فطام' يدوياً من صفحة 'دورة الإنتاج' ← 'خطة السوق'، "
            "أو ينتظر عمر أكبر (افتراضي 90 يوم، قابل للتعديل أيضاً) فيعتبره النظام مفطوماً تلقائياً بدون تسجيل يدوي."
        ),
        translations={
            "en": {
                "title": "A newborn's journey in the system — from registration to weaning",
                "body": (
                    "No — the initial registration is **manual** ('+ New animal' button, source 'born on farm', linked to its mother) — the system "
                    "doesn't detect the birth on its own. But after registration, everything after is fully automatic:\n"
                    "• It and its mother move automatically to the first 'isolation' barn, and 7 daily check tasks + a vet exam within 48 hours + "
                    "a weighing task + vaccination (mother and newborn) are opened (see 'automatic isolation' for full details).\n"
                    "• It never had a purchase price (left empty) — its cost is computed automatically from actual feed consumption (FCR report).\n"
                    "• Weaning: the 'nursing & weaning' stage gate (stage 8 in the production cycle) needs a minimum age (default 60 days, adjustable "
                    "in settings) — either you log a 'weaning date' manually from the 'production cycle' → 'market plan' page, or it waits for an "
                    "older age (default 90 days, also adjustable) and the system considers it weaned automatically without manual logging."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_record_disease",
        title="كيف أسجّل مرض أو علاج؟",
        keywords=["تسجيل مرض", "اسجل مرض", "كيف اسجل علاج", "اضافة مرض", "حالة مرضية جديدة"],
        body=(
            "من شاشة 'الصحة' ← 'الأمراض' ← '+ سجل مرضي جديد' (/health/diseases/new):\n"
            "• اختر الحيوان، اسم المرض، والدواء المستخدم (لو فيه) — النظام يخصم الكمية من الصيدلية تلقائياً ويحسب فترة السحب لو الدواء يتطلبها.\n"
            "• السجل يبقى 'نشط' لين تغلقه صراحة من نفس الشاشة (زر إغلاق + ملاحظة تعافٍ) — ما يُغلق تلقائياً لمجرد مرور وقت.\n"
            "• إغلاق المرض بدواء له فترة سحب يُنشئ تلقائياً تذكيراً بتاريخ انتهاء الفترة — تلقاه بشاشة مراجعة المهام.\n"
            "• حقل 'تكلفة العلاج': لو اخترت دواء وكمية، التكلفة تُحسب تلقائياً من سعر الدواء (وما تُسجَّل عملية مالية إضافية — قيمة الدواء اتُّحسبت فعلياً وقت شرائه). لو كتبتها يدوياً بدون دواء (أجرة علاج خارجي مثلاً)، تُنشأ عملية 'مصروف' مالية حقيقية بفئة 'علاج مرض'."
        ),
        translations={
            "en": {
                "title": "How do I log a disease or treatment?",
                "body": (
                    "From 'Health' → 'Diseases' → '+ New disease record':\n"
                    "• Pick the animal, disease name, and medicine used (if any) — the system deducts the quantity from the pharmacy automatically and computes the withdrawal period if the medicine requires one.\n"
                    "• The record stays 'active' until you explicitly close it from the same screen (close button + recovery note) — it doesn't close automatically just because time passed.\n"
                    "• Closing a disease with a medicine that has a withdrawal period automatically creates a reminder for the period's end date — you'll find it on the task review screen.\n"
                    "• 'Treatment cost' field: if you picked a medicine and quantity, the cost is computed automatically from the medicine's price (no extra financial transaction is logged — the medicine's value was already accounted for when it was purchased). If you type it manually without a medicine (an external treatment fee, for example), a real 'expense' financial transaction is created under the 'disease treatment' category."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_assign_task",
        title="كيف أوزّع مهمة على عامل؟",
        keywords=["توزيع مهمة", "اضافة مهمة", "كيف اوزع مهمة", "تعيين مهمة", "مهمة جديدة لعامل"],
        body=(
            "من شاشة 'المهام' زر '+ توزيع مهمة' يفتح نافذة سريعة (بدون الخروج من الشاشة):\n"
            "• حدد العنوان والعامل (أو الحظيرة، ويتحدد العامل تلقائياً من مسؤول الحظيرة لو ما اخترت عامل بالاسم).\n"
            "• المهمة توصل للعامل فوراً بحالة 'قيد الانتظار' — ما تحتاج اعتماد إضافي لأنك أنت اللي وزّعتها مباشرة.\n"
            "• لو تبي مهمة يومية متكررة (تنظيف، فحص...) بدل مهمة لمرة وحدة، استخدم شاشة 'مهام العامل التلقائية' (زر ⚙️ بأعلى شاشة المهام) بدلها."
        ),
        translations={
            "en": {
                "title": "How do I assign a task to a worker?",
                "body": (
                    "From the 'tasks' screen, the '+ assign task' button opens a quick dialog (without leaving the screen):\n"
                    "• Set the title and the worker (or the barn, and the worker is set automatically from the barn's responsible worker if you didn't pick one by name).\n"
                    "• The task reaches the worker immediately with status 'pending' — it doesn't need extra approval since you assigned it directly yourself.\n"
                    "• If you want a recurring daily task (cleaning, checking...) instead of a one-time task, use the 'automatic worker tasks' screen (⚙️ button at the top of the tasks screen) instead."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_record_sale",
        title="كيف أسجّل عملية بيع؟",
        keywords=["تسجيل بيع", "اسجل بيع", "كيف ابيع راس", "بيع حيوان", "عملية بيع", "بيع رأس"],
        body=(
            "من صفحة الحيوان نفسه (افتحه من شاشة 'الحيوانات') → تبويب 'دورة الإنتاج' → زر 'بيع':\n"
            "• الرأس لازم يكون وصل مرحلة 'قرار المصير' (آخر مرحلة بدورة الإنتاج) قبل ما يقبل النظام البيع — بوابة أمان تلقائية.\n"
            "• لو الرأس تحت فترة سحب دواء نشطة، البيع يُرفض تلقائياً حتى تنتهي الفترة.\n"
            "• البيع يسجّل حركة مالية تلقائياً — ما تحتاج تدخلها يدوياً بشاشة المالية منفصلة."
        ),
        translations={
            "en": {
                "title": "How do I log a sale?",
                "body": (
                    "From the animal's own page (open it from the 'animals' screen) → 'production cycle' tab → 'sell' button:\n"
                    "• The head must have reached the 'fate decision' stage (the last stage in the production cycle) before the system accepts the sale — an automatic safety gate.\n"
                    "• If the head is under an active medicine withdrawal period, the sale is rejected automatically until the period ends.\n"
                    "• The sale logs a financial transaction automatically — you don't need to enter it manually on a separate finance screen."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_pharmacy_stock",
        title="كيف أضيف أو أحدّث مخزون الصيدلية؟",
        keywords=["اضافة دواء", "مخزون الصيدلية", "تحديث الصيدلية", "شراء دواء", "كيف اضيف دواء"],
        body=(
            "دواء جديد كلياً: من 'الصحة' ← 'الصيدلية' ← '+ دواء جديد'.\n"
            "لتسجيل عملية شراء دواء موجود أصلاً (يزيد الكمية بدون الكتابة فوق الرقم الحالي): افتح الدواء ← تعديل ← زر '📦 تسجيل عملية شراء' — يسجّل تاريخ الشراء وتاريخ انتهاء الصلاحية لتلك الدفعة تحديداً، وينبّهك تلقائياً لما تقرب صلاحيتها."
        ),
        translations={
            "en": {
                "title": "How do I add or update pharmacy stock?",
                "body": (
                    "A completely new medicine: from 'Health' → 'Pharmacy' → '+ New medicine'.\n"
                    "To log a purchase of a medicine that already exists (adds to the quantity without overwriting the current number): open the medicine → edit → '📦 Log purchase' button — logs that specific batch's purchase date and expiry date, and warns you automatically as its expiry approaches."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_worker_report",
        title="كيف أرفع بلاغ (كعامل)؟",
        keywords=["رفع بلاغ", "تسجيل بلاغ", "كيف ابلغ", "بلاغ جديد", "ملاحظة عن حيوان"],
        body=(
            "من الشاشة الرئيسية المبسّطة للعامل، اضغط أحد الأزرار الأربعة الجاهزة (فحص/حالة صحية، نقل للعزل، تغذية، بيض/حضانة) — كل زر يفتح فورم بلاغ سريع بنوع محدد مسبقاً، ما تحتاج تختار من قائمة.\n"
            "البلاغ يوصل مباشرة للدكتور/المالك بشاشة 'البلاغات' ويقدر يحوّله أو يغلقه بعد المعالجة."
        ),
        translations={
            "en": {
                "title": "How do I file a report (as a worker)?",
                "body": (
                    "From the worker's simplified home screen, press one of the four ready buttons (checkup/health status, move to isolation, feeding, "
                    "eggs/incubation) — each opens a quick report form with a pre-set type, no need to pick from a list.\n"
                    "The report reaches the doctor/owner directly on the 'reports' screen and they can transfer or close it after handling it."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_alerts_screen",
        title="وين ألقى التنبيهات؟",
        keywords=["شاشة التنبيهات", "ايش التنبيهات", "فهم التنبيهات", "تنبيهات النظام", "صفحة اليوم"],
        body=(
            "التنبيهات صارت جزء من 'صفحة اليوم' (القائمة الجانبية) بدل شاشة منفصلة — عرض حي يُشتق كل مرة من بياناتك الفعلية: تحصينات مستحقة، فترات سحب قاربت تنتهي، ولادات متوقعة، أمراض مفتوحة من فترة، نقص مخزون متوقع، مهام متعذّرة، تباطؤ نمو مشبوه، بيانات حيوانات ناقصة، وأكثر.\n"
            "كل تنبيه جنبه زر 'فتح' يوديك مباشرة لصفحة الحيوان أو الحظيرة المرتبطة."
        ),
        translations={
            "en": {
                "title": "Where do I find alerts?",
                "body": (
                    "Alerts became part of 'today's page' (side menu) instead of a separate screen — a live view derived every time from your actual "
                    "data: vaccinations due, withdrawal periods about to end, expected births, diseases open for a while, expected stock shortages, "
                    "stalled tasks, suspicious slow growth, missing animal data, and more.\n"
                    "Each alert has an 'open' button next to it that takes you straight to the linked animal or barn page."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_incomplete_data_alerts",
        title="ليش يطلعلي تنبيه 'بيانات ناقصة'؟",
        keywords=["بيانات ناقصة", "تنبيه ناقص", "حقل ناقص حيوان", "ليش يطلب سعر"],
        body=(
            "أي حيوان مسجَّل بدون الجنس أو الوزن أو الغرض (تربية/تسمين/بيع) يطلع له تنبيه — بغض النظر عن مصدره. السعر مطلوب بس للشراء/الهدية/الرصيد الافتتاحي (المولود بالمزرعة ما له سعر شراء أصلاً، تكلفته تُحسب من استهلاك العلف).\n"
            "الحفظ نفسه ما يتوقف — تقدر تسجّل الحيوان عادي وتكمّل البيانات لاحقاً من شاشة تعديل الحيوان، والتنبيه يختفي تلقائياً بمجرد الإكمال."
        ),
        translations={
            "en": {
                "title": "Why do I get a 'missing data' alert?",
                "body": (
                    "Any animal logged without sex, weight, or purpose (breeding/fattening/sale) gets an alert — regardless of its source. Price is only "
                    "required for purchase/gift/opening balance (a farm-born newborn never had a purchase price, its cost is computed from feed "
                    "consumption).\n"
                    "Saving itself is never blocked — you can log the animal normally and complete the data later from the animal edit screen, and the "
                    "alert disappears automatically once it's completed."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_add_team_member",
        title="كيف أضيف عضو فريق جديد (عامل/دكتور)؟",
        keywords=["اضافة عضو", "عضو فريق جديد", "حساب جديد لعامل", "كيف اضيف دكتور", "اضافة موظف"],
        body=(
            "من 'الفريق' ← 'أعضاء الفريق' ← '+ عضو جديد':\n"
            "• رقم الجوال هو معرّف الدخول (بدون بريد إلكتروني) — اختر كلمة مرور له بنفسك.\n"
            "• حدد الدور (عامل/دكتور/ممرض/محاسب...) — يحدد تلقائياً أي شاشات يقدر يشوفها.\n"
            "• نسيت كلمة مرور حساب؟ من نفس شاشة الأعضاء ← تعديل العضو ← حقل كلمة مرور جديد (اختياري، يتغيّر بس لو عبّيته)."
        ),
        translations={
            "en": {
                "title": "How do I add a new team member (worker/doctor)?",
                "body": (
                    "From 'Team' → 'Team members' → '+ New member':\n"
                    "• The phone number is the login identifier (no email) — set a password for them yourself.\n"
                    "• Set the role (worker/doctor/nurse/accountant...) — automatically determines which screens they can see.\n"
                    "• Forgot an account's password? From the same members screen → edit the member → 'new password' field (optional, only changes if you fill it in)."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_family_view",
        title="شاشة المتابعة المبسّطة (لغير المستخدمين المعتادين على التطبيقات)",
        keywords=["شاشة والدي", "متابعة مبسطة", "خط كبير", "شاشة كبار السن", "family view"],
        body=(
            "رابط `/family-view` (أو زر '👋 شاشة متابعة مبسّطة' بشاشة الإعدادات) — صفحة عرض فقط بخط كبير جداً، بدون أي تعقيد تنقّل:\n"
            "• زر 'المهام' يفتح تقدّم كل دور (المالك/الطبيب/العامل) — منجز، متعذّر، وباقي، مع أزرار تأجيل/إلغاء حقيقية.\n"
            "• زر 'المخزون' يفتح 3 أقسام (علف/صيدلية/معدات) بالمتبقي والمستهلك يومياً وشهرياً.\n"
            "• زر صغير أعلى اليسار يبدّل وضع ليلي/نهاري، يُحفَظ تلقائياً بنفس الجهاز."
        ),
        translations={
            "en": {
                "title": "Simplified follow-up screen (for people not used to apps)",
                "body": (
                    "The `/family-view` link (or the '👋 simplified follow-up screen' button on the settings screen) — a view-only page with very large "
                    "text, no navigation complexity:\n"
                    "• The 'tasks' button opens each role's progress (owner/doctor/worker) — done, failed, and remaining, with real postpone/cancel buttons.\n"
                    "• The 'stock' button opens 3 sections (feed/pharmacy/equipment) with what's left and daily/monthly consumption.\n"
                    "• A small button top-left switches night/day mode, saved automatically on that same device."
                ),
            },
        },
    ),

    # ---------- توسعة مرشد الاستخدام (بند إضافي 115) ----------
    # استكمال بند 114 — تغطية بقية الوحدات الرئيسية (الصحة، التكاثر،
    # العلف، المالية، التقارير، الدفعات، المستودعات، النعام، المناخ،
    # النسخ الاحتياطي، الصلاحيات) بنفس النمط بالضبط.
    KBEntry(
        code="howto_vet_visit",
        title="كيف أسجّل زيارة بيطرية؟",
        keywords=["تسجيل زيارة", "زيارة بيطرية جديدة", "اسجل زيارة", "كيف اسجل زيارة دكتور"],
        body=(
            "من 'الصحة' ← 'الزيارات البيطرية' ← '+ زيارة جديدة':\n"
            "• حدد الحيوان، الدكتور، والتشخيص — الدواء المستخدم (لو فيه) يخصم من الصيدلية ويحسب فترة السحب تلقائياً، نفس مبدأ تسجيل المرض.\n"
            "• الزيارة سجل تاريخي بس (ما تبقى 'مفتوحة' زي المرض) — لتوثيق فحص أو كشف عام مو علاجاً ممتداً.\n"
            "• حقل 'التكلفة': نفس مبدأ تسجيل المرض — لو محسوبة من دواء استُخدم، ما تُنشأ عملية مالية إضافية (اتُّحسبت وقت الشراء). لو أجرة كشف يدوية بدون دواء، تُنشأ عملية 'مصروف' مالية حقيقية بفئة 'زيارة بيطرية' تظهر بشاشة المالية تلقائياً."
        ),
        translations={
            "en": {
                "title": "How do I log a vet visit?",
                "body": (
                    "From 'Health' → 'Vet visits' → '+ New visit':\n"
                    "• Pick the animal, the doctor, and the diagnosis — the medicine used (if any) is deducted from the pharmacy and its withdrawal period is computed automatically, same principle as logging a disease.\n"
                    "• The visit is a historical record only (doesn't stay 'open' like a disease) — for documenting an exam or general checkup, not extended treatment.\n"
                    "• 'Cost' field: same principle as logging a disease — if computed from a medicine used, no extra financial transaction is created (already accounted for at purchase). If a manual exam fee without a medicine, a real 'expense' financial transaction is created under the 'vet visit' category and shows on the finance screen automatically."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_smart_diagnose",
        title="كيف أستخدم أداة التشخيص الذكي؟",
        keywords=["تشخيص ذكي", "شجرة تشخيص", "مطابقة اعراض", "اداة التشخيص"],
        body=(
            "من 'الصحة' ← 'تشخيص ذكي' (/health/diagnose): اختر الأعراض الظاهرة على الحيوان من القائمة، والنظام يرشّح أقرب الأمراض احتمالاً حسب مطابقة أعراض معروفة مسبقاً (بعض الأمراض لها عرض 'إجباري' مميّز — لو ما اخترته، نسبة التطابق تنخفض تلقائياً حتى لو باقي الأعراض متطابقة) — **ترشيح بس، مو تشخيص نهائي ولا وصفة علاج**، القرار الطبي يبقى للدكتور دايماً."
        ),
        translations={
            "en": {
                "title": "How do I use the smart diagnosis tool?",
                "body": (
                    "From 'Health' → 'Smart diagnose' (/health/diagnose): pick the symptoms visible on the animal from the list, and the system suggests the closest likely diseases by matching them against pre-known symptoms (some diseases have a distinctive 'required' symptom — if you don't pick it, the match percentage drops automatically even if the rest of the symptoms match) — **a suggestion only, not a final diagnosis or a treatment prescription**, the medical decision always stays with the doctor."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_vaccination_schedule",
        title="كيف أجدول تحصين جماعي مسبقاً؟",
        keywords=["جدولة تحصين", "تحصين جماعي", "تقويم تحصينات", "موعد تحصين مستقبلي", "موعد تحصين قادم"],
        body=(
            "نعم، تقدر بخطوتين:\n"
            "1. تحصين جماعي فوري: من 'الإجراء الجماعي' أشّر الرؤوس المطلوبة واختر 'تحصين جماعي' من قائمة الإجراءات — يسجَّل تحصين فعلي الآن لكل الرؤوس المحددة دفعة وحدة.\n"
            "2. جدولة موعد تحصين قادم (تذكير مستقبلي بدون تسجيل فعلي الآن): من 'الصحة' ← 'تقويم التحصينات' ← '+ جدولة جديدة': اختر الحظيرة، الدواء، والتاريخ المخطَّط. قبل الموعد بمدة كافية، النظام يقارن تلقائياً عدد رؤوس الحظيرة الحيّ × الجرعة الافتراضية مقابل مخزون الصيدلية، وينبّهك لو المخزون بيصير ناقص."
        ),
        translations={
            "en": {
                "title": "How do I schedule a group vaccination in advance?",
                "body": (
                    "Yes, in two steps:\n"
                    "1. Immediate group vaccination: from 'group action' check the required heads and pick 'group vaccination' from the actions list — logs an actual vaccination now for all selected heads at once.\n"
                    "2. Scheduling an upcoming vaccination date (a future reminder without an actual record now): from 'Health' → 'Vaccination calendar' → '+ New schedule': pick the barn, medicine, and planned date. With enough lead time before the date, the system automatically compares the barn's live head count × the default dose against the pharmacy stock, and warns you if stock will fall short."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_treatment_protocol",
        title="كيف أطبّق بروتوكول علاج جاهز؟",
        keywords=["تطبيق بروتوكول", "بروتوكول علاج جاهز", "خطوات علاج متعددة"],
        body=(
            "من 'الصحة' ← 'البروتوكولات' افتح بروتوكولاً جاهزاً (أو أنشئ وحدة جديدة بخطواته) ← زر 'تطبيق على رأس'. النظام يولّد مهمة منفصلة لكل خطوة بتاريخها — وبعد آخر خطوة (منجزة أو فاشلة) يولّد تلقائياً مهمة 'تقييم فعالية العلاج' تذكّرك تراجع النتيجة."
        ),
        translations={
            "en": {
                "title": "How do I apply a ready treatment protocol?",
                "body": (
                    "From 'Health' → 'Protocols' open a ready protocol (or create a new one with its steps) → 'apply to a head' button. The system generates a separate task for each step with its date — and after the last step (completed or failed) it automatically generates a 'treatment effectiveness review' task to remind you to review the outcome."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_mating_pregnancy",
        title="كيف أسجّل تلقيح وتشخيص حمل؟",
        keywords=["تسجيل تلقيح", "تشخيص حمل", "اسجل تقريع", "حمل جديد", "تلقيح جديد", "اسجل تلقيح"],
        body=(
            "'التكاثر' ← 'التلقيح' ← '+ تسجيل تلقيح' لتسجيل تقريع الأنثى بفحل معيّن بتاريخه.\n"
            "بعدها 'التكاثر' ← 'الحمل' ← '+ تشخيص حمل جديد' لتأكيد الحمل (بفحص يدوي أو سونار) — تاريخ الولادة المتوقع يُحسب تلقائياً من مدة الحمل المضبوطة بالإعدادات."
        ),
        translations={
            "en": {
                "title": "How do I log mating and pregnancy diagnosis?",
                "body": (
                    "'Breeding' → 'Mating' → '+ Log mating' to log a female's mating with a specific sire, with its date.\n"
                    "Then 'Breeding' → 'Pregnancy' → '+ New pregnancy diagnosis' to confirm the pregnancy (by manual exam or sonar) — the expected birth date is computed automatically from the gestation period set in settings."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_sonar",
        title="كيف أسجّل فحص سونار؟",
        keywords=["تسجيل سونار", "فحص سونار جديد", "اضافة سونار", "فحص سونار", "اسجل سونار"],
        body=(
            "'التكاثر' ← 'السونار' ← '+ فحص جديد': اختر الأنثى، النتيجة (حامل/غير حامل/غير مؤكد)، وتاريخ إعادة الفحص لو النتيجة غير مؤكدة — النظام يولّد تلقائياً مهمة تذكير بتاريخ إعادة الفحص بالضبط."
        ),
        translations={
            "en": {
                "title": "How do I log a sonar exam?",
                "body": (
                    "'Breeding' → 'Sonar' → '+ New exam': pick the female, the result (pregnant/not pregnant/unconfirmed), and a re-exam date if the result is unconfirmed — the system automatically generates a reminder task for the exact re-exam date."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_feed_item_new",
        title="كيف أضيف مكوّن علف جديد ووش معنى الوحدة الثابتة؟",
        keywords=[
            "اضافة مكون علف", "مكون علف جديد", "اضف علف", "صنف علف جديد",
            "وحدة العلف", "وحدة ثابتة", "ربطة برسيم", "كم كيلو بالربطة", "وزن الوحدة",
            "كيف اضيف اعلاف", "اضيف اعلاف", "اضافة اعلاف", "كيف اضيف علف", "اضيف علف",
        ],
        body=(
            "'العلف' ← 'مكوّنات العلف' ← '+ مكوّن جديد': الاسم، السعر لكل وحدة، والكمية المتوفرة — هذا الأساسي.\n"
            "'الوحدة' قائمة ثابتة (كجم/طن/لتر/مل/كيس/ربطة) مو نص حر تكتبه بنفسك — عشان النظام يقدر يجمع نفس الصنف بثقة (كم متوفر، كم يُصرف يومياً، ومتى ينبّهك تشتري كمية محددة زي '80 كيلو شعير' لتغطية باقي الشهر). لو تكتب 'كيلو' مرة و'كجم' مرة ثانية لنفس الصنف، النظام كان يعاملهم كوحدتين مختلفتين بالغلط.\n"
            "لو الوحدة من نوع عدّي وزنه مو ثابت عالمياً (زي 'ربطة' برسيم أو 'كيس')، فيه حقل اختياري 'وزن الوحدة الواحدة بالكيلو' يسجّل مرجعك الشخصي (مثلاً ربطة = 15 كجم) — للرجوع له وقت الشراء بس، ما يدخل بأي حساب تلقائي بالنظام."
        ),
        translations={
            "en": {
                "title": "How do I add a new feed component and what does 'fixed unit' mean?",
                "body": (
                    "'Feed' → 'Feed components' → '+ New component': name, price per unit, and available quantity — the basics.\n"
                    "The 'unit' is a fixed list (kg/ton/liter/ml/bag/bundle), not free text you type yourself — so the system can reliably total the same item (how much is available, how much is used daily, and when to warn you to buy a specific amount like '80 kg of barley' to cover the rest of the month). If you type 'kilo' once and 'kg' another time for the same item, the system used to treat them as two different units by mistake.\n"
                    "If the unit is a count-type whose weight isn't universally fixed (like a bundle of alfalfa or a bag), there's an optional 'weight of one unit in kg' field to log your own reference (e.g. one bundle = 15 kg) — for your own reference at purchase time only, it doesn't enter any automatic calculation in the system."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_feed_ration",
        title="كيف أبني وصفة علف وأربطها بحظيرة؟",
        keywords=["وصفة علف", "بناء وصفة", "ابني وصفة", "اضافة وصفة", "وصفة جديدة", "خطة تغذية حظيرة", "ربط علف بحظيرة"],
        body=(
            "'العلف' ← 'الوصفات' ← '+ وصفة جديدة': أضف مكوّنات العلف ونسبة كل وحدة من إجمالي الوزن.\n"
            "بعدها 'العلف' ← 'خطط التغذية' ← '+ خطة جديدة' لربط الوصفة بحظيرة معيّنة وكمية يومية لكل رأس — أساس حساب معدل التحويل الغذائي (FCR) تلقائياً لاحقاً."
        ),
        translations={
            "en": {
                "title": "How do I build a feed ration and link it to a barn?",
                "body": (
                    "'Feed' → 'Rations' → '+ New ration': add feed components and each one's percentage of total weight.\n"
                    "Then 'Feed' → 'Feed plans' → '+ New plan' to link the ration to a specific barn and a daily amount per head — the basis for automatically computing feed conversion (FCR) later."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_feed_optimizer",
        title="كيف يشتغل موازِن العليقة؟",
        keywords=["موازن العليقة", "احسب اخلط علف", "خلطة اقتصادية", "محسّن العلف"],
        body=(
            "'العلف' ← 'موازِن العليقة': أدخل الاحتياج الغذائي المستهدف (بروتين/طاقة/كالسيوم...) والأصناف المتوفرة عندك بأسعارها — النظام يحسب أرخص خلطة تحقق الاحتياج فعلياً (برمجة خطية حقيقية، مو تخمين)، وتقدر تعدّل النتيجة يدوياً بعدها.\n"
            "هذا حساب يدوي لرأس واحد تختاره — لو تبي حساب تلقائي لكل حظيرة كاملة، راجع مواعيد وجبات العلف."
        ),
        translations={
            "en": {
                "title": "How does the ration optimizer work?",
                "body": (
                    "'Feed' → 'Ration optimizer': enter the target nutritional requirement (protein/energy/calcium...) and the items you have available with their prices — the system computes the cheapest mix that actually meets the requirement (real linear programming, not a guess), and you can adjust the result manually afterward.\n"
                    "This is a manual calculation for one head you pick — if you want an automatic calculation for a whole barn, see feeding schedule times."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_feed_blend_auto",
        title="كيف يحسب النظام كمية العلف تلقائياً لكل حظيرة؟",
        keywords=["حساب علف تلقائي", "كمية علف الحظيرة", "خلطة الحظيرة", "علف يومي تلقائي", "النظام يقرر العلف"],
        body=(
            "بدل ما تدخل العلف يدوياً لكل رأس، النظام يجمع احتياج كل رؤوس الحظيرة النشطة (وزن كل رأس + حالته الفسيولوجية) ويحسب خلطة واحدة تغطي الحظيرة كاملة من مكوّنات العلف المتوفرة فعلاً بالمخزون — نفس محرك 'موازِن العليقة' بس مجمَّع لحظيرة كاملة بدل رأس واحد.\n"
            "تشوف الخلطة المحسوبة بتفاصيل مهمة 'وجبة علف' قبل ما توزّعها فعلياً، ولما تنجزها المخزون ينخصم تلقائياً."
        ),
        translations={
            "en": {
                "title": "How does the system compute feed quantity automatically per barn?",
                "body": (
                    "Instead of entering feed manually for each head, the system totals the requirement of every active head in the barn (each head's weight + its physiological state) and computes one mix that covers the whole barn from feed components actually available in stock — the same 'ration optimizer' engine, just aggregated for a whole barn instead of one head.\n"
                    "You see the computed mix in the 'feed meal' task details before you actually distribute it, and stock is deducted automatically when you complete it."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_finance_entry",
        title="كيف أسجّل عملية مالية (مصروف/دخل)؟",
        keywords=["تسجيل عملية مالية", "اضافة مصروف", "اضافة دخل", "قيد مالي جديد", "عملية مالية جديدة", "اسجل عملية مالية"],
        body=(
            "'المالية' ← '+ عملية جديدة': حدد النوع (شراء/مصروف/دين مستلم/سداد دين...)، المبلغ، والحيوان المرتبط لو فيه.\n"
            "أغلب العمليات لها شاشتها المخصّصة اللي تسجّل المالية تلقائياً معاها — بيع رأس، شراء دواء أو علف أو معدات، صيانة أصل، فاتورة كهرباء/ماء، وراتب شهري (من 'الفريق' ← 'رواتب الشهر'، مو من هنا). هذي الشاشة العامة تبقى للعمليات المتفرقة اللي ما لها شاشة مخصّصة."
        ),
        translations={
            "en": {
                "title": "How do I log a financial transaction (expense/income)?",
                "body": (
                    "'Finance' → '+ New transaction': set the type (purchase/expense/debt received/debt repayment...), the amount, and the linked animal if any.\n"
                    "Most transactions have their own dedicated screen that logs the finance automatically alongside them — selling a head, buying medicine, feed, or equipment, asset maintenance, an electricity/water bill, and monthly salary (from 'Team' → 'monthly payroll', not here). This general screen stays for scattered transactions that don't have a dedicated screen."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_export_reports",
        title="كيف أصدّر تقرير Excel أو PDF؟",
        keywords=["تصدير تقرير", "تصدير اكسل", "تصدير pdf", "طباعة تقرير", "اصدر تقرير", "تقرير excel"],
        body=(
            "بأي شاشة تقارير ('التقارير' ← اختر النوع)، حدد الفترة الزمنية من فلتر أعلى الشاشة، بعدها زر 'تصدير Excel' أو 'تصدير PDF' بأعلى الجدول — يصدّر نفس البيانات المعروضة بالفلترة المختارة بالضبط."
        ),
        translations={
            "en": {
                "title": "How do I export an Excel or PDF report?",
                "body": (
                    "On any reports screen ('Reports' → pick the type), set the date range from the filter at the top of the screen, then the 'Export Excel' or 'Export PDF' button at the top of the table — exports exactly the data shown with the chosen filtering."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_batch_receiving",
        title="كيف أستقبل دفعة حيوانات جديدة بمراحل؟",
        keywords=["استقبال دفعة", "دفعة حيوانات جديدة", "شراء جماعي", "قطيع جديد"],
        body=(
            "'الدفعات' ← '+ دفعة جديدة': سجّل عدد الرؤوس المستقبلة كدفعة واحدة بدل تسجيل كل رأس لحاله. بعدها تقدر 'توزّع' الدفعة على أرقام رؤوس فردية تدريجياً، أو 'تقدّم' حالتها الجماعية (رش، تحصين مبدئي) لكل الدفعة دفعة وحدة."
        ),
        translations={
            "en": {
                "title": "How do I receive a new batch of animals in stages?",
                "body": (
                    "'Batches' → '+ New batch': log the number of heads received as one batch instead of logging each head on its own. Then you can gradually 'break down' the batch into individual head numbers, or 'advance' its collective status (spraying, initial vaccination) for the whole batch at once."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_warehouse_transfer",
        title="كيف أحوّل مخزون بين مستودعين؟",
        keywords=["تحويل مخزون", "نقل بين مستودعين", "تحويل علف بين فروع", "احول مخزون", "بين مستودعين"],
        body=(
            "'المستودعات' ← افتح الصنف ← زر 'تحويل': اختر المستودع الوجهة والكمية. التحويل يحافظ على الرصيد الإجمالي للصنف (ما يزيد ولا ينقص المجموع الكلي)، بس يعيد توزيعه بين المستودعات."
        ),
        translations={
            "en": {
                "title": "How do I transfer stock between two warehouses?",
                "body": (
                    "'Warehouses' → open the item → 'transfer' button: pick the destination warehouse and the quantity. The transfer keeps the item's total balance unchanged (doesn't add to or subtract from the grand total), just redistributes it between warehouses."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_ostrich_egg",
        title="كيف أسجّل بيضة نعام جديدة وأدخلها الحاضنة؟",
        keywords=["تسجيل بيضة", "بيضة نعام جديدة", "ادخال حاضنة"],
        body=(
            "'النعام' ← 'البيض' ← '+ بيضة جديدة' لتسجيلها فور الجمع (رقم مستقل لكل بيضة).\n"
            "بعدها زر 'وضع بالحاضنة' يربطها بحاضنة معيّنة ويبدأ عدّ تاريخ الفقس المتوقع تلقائياً حسب مدة الحضانة المضبوطة بالإعدادات."
        ),
        translations={
            "en": {
                "title": "How do I log a new ostrich egg and load it into an incubator?",
                "body": (
                    "'Ostrich' → 'Eggs' → '+ New egg' to log it as soon as you collect it (its own number for each egg).\n"
                    "Then the 'place in incubator' button links it to a specific incubator and starts counting the expected hatch date automatically per the incubation duration set in settings."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_climate_settings",
        title="كيف أفعّل رادار المناخ والإجهاد الحراري؟",
        keywords=["رادار المناخ", "اعداد الطقس", "تفعيل الاجهاد الحراري", "موقع المزرعة الطقس"],
        body=(
            "'المناخ' ← 'الإعدادات': أدخل موقع مزرعتك (يجلب توقعات الطقس تلقائياً من مصدر مجاني بدون مفتاح). بعد التفعيل، الشاشة الرئيسية تحسب مؤشر الإجهاد الحراري (THI) يومياً وتولّد مهام وقائية تلقائية (تعديل توقيت العلف، إضافة ماء، فحص تهوية/تظليل) لما المؤشر يتجاوز الحدود المضبوطة."
        ),
        translations={
            "en": {
                "title": "How do I turn on the climate & heat stress radar?",
                "body": (
                    "'Climate' → 'Settings': enter your farm's location (fetches weather forecasts automatically from a free source, no key needed). After enabling it, the home screen computes the heat stress index (THI) daily and generates automatic preventive tasks (adjusting feed timing, adding water, checking ventilation/shade) when the index exceeds the set thresholds."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_backup",
        title="كيف آخذ نسخة احتياطية أو أستوردها؟",
        keywords=["نسخة احتياطية", "backup", "تنزيل نسخة", "حفظ نسخة من البيانات"],
        body=(
            "من الإعدادات ← 'النسخ الاحتياطي' ← زر 'إنشاء نسخة الآن' — يحفظ نسخة كاملة من قاعدة بياناتك بتاريخها، وتقدر تنزّلها لجهازك من نفس الشاشة. يُنصح تاخذ نسخة بشكل دوري، خصوصاً قبل أي تعديل كبير."
        ),
        translations={
            "en": {
                "title": "How do I take or restore a backup?",
                "body": (
                    "From Settings → 'Backup' → 'Create backup now' button — saves a full copy of your database with its date, and you can download it to your device from the same screen. It's recommended to take a backup periodically, especially before any major change."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_roles_permissions",
        title="كيف أنشئ دوراً وظيفياً جديداً بصلاحيات مخصّصة؟",
        keywords=["دور جديد", "صلاحيات مخصصة", "مسمى وظيفي جديد", "تعديل صلاحيات دور", "دورا وظيفيا جديدا", "انشئ دور"],
        body=(
            "من الإعدادات ← 'الأدوار والصلاحيات' ← '+ دور جديد': اختر اسم الدور وحدد أي صلاحيات يملكها (عرض الحيوانات، إدارة الصحة، توزيع مهام...) من قائمة كاملة — بدون أي كود، كله من الواجهة. الأدوار الستة الجاهزة (مالك، دكتور، عامل، ممرض، محاسب، مشاهد) تبقى نقطة بداية تقدر تعدّلها أو تنشئ غيرها."
        ),
        translations={
            "en": {
                "title": "How do I create a new job role with custom permissions?",
                "body": (
                    "From Settings → 'Roles & permissions' → '+ New role': pick a role name and set which permissions it has (viewing animals, managing health, assigning tasks...) from a full list — no code needed, all from the interface. The six ready roles (owner, doctor, worker, nurse, accountant, viewer) stay a starting point you can edit or build others from."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_setup_checklist",
        title="وش هي قائمة 'خطوات تجهيز النظام' بالصفحة الرئيسية؟",
        keywords=["خطوات التجهيز", "قائمة البداية", "دليل اول استخدام"],
        body=(
            "تظهر بأعلى الصفحة الرئيسية أول ما تشغّل النظام — دليل سريع يتحقق تلقائياً (✅/⬜) هل أضفت أول حظيرة، أول رأس، أول عضو فريق، أول دواء، وأول صنف علف. تقدر تتجاهلها بزر 'ما أحتاجها' لو ما تحتاجها، وترجع لها لاحقاً من نفس المكان."
        ),
        translations={
            "en": {
                "title": "What's the 'system setup steps' list on the home page?",
                "body": (
                    "Appears at the top of the home page as soon as you start using the system — a quick guide that automatically checks (✅/⬜) whether you've added your first barn, first animal, first team member, first medicine, and first feed item. You can dismiss it with the 'I don't need it' button if you don't need it, and come back to it later from the same place."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_readiness_check",
        title="كيف أستخدم 'فحص الجاهزية قبل النشر'؟",
        keywords=["فحص الجاهزية", "جاهزية قبل النشر", "تحقق قبل التشغيل الفعلي"],
        body=(
            "من الإعدادات ← 'فحص الجاهزية قبل النشر' — قائمة تحقق آلية لنقاط شائعة تُنسى (كلمة مرور افتراضية، حظيرة عزل، حيوانات بلا حظيرة، فريق العمل، نسخة احتياطية...). عرض بس، بدون أي تعديل تلقائي على بياناتك — القرار يبقى لك."
        ),
        translations={
            "en": {
                "title": "How do I use the 'go-live readiness check'?",
                "body": (
                    "From Settings → 'go-live readiness check' — an automatic checklist for commonly forgotten points (default password, isolation barn, animals with no barn, team members, a backup...). Display only, with no automatic change to your data — the decision stays yours."
                ),
            },
        },
    ),

    # ---------- توسعة ثانية لمرشد الاستخدام (بند إضافي 116) ----------
    KBEntry(
        code="howto_bulk_operations",
        title="كيف أطبّق عملية على عدة رؤوس مرة وحدة؟",
        keywords=["عملية جماعية", "تحديد عدة رؤوس", "تطبيق جماعي", "عمليات جماعية", "الاجراء الجماعي"],
        body=(
            "من القائمة الجانبية افتح 'الإجراء الجماعي' (شاشة مستقلة عن 'الحيوانات' العادية) — أشّر الرؤوس بعلامة ✓ (أو فلترة حسب حظيرة/فصيلة ثم تحديد الكل)، بعدها اختر العملية من القائمة (وزن، تحصين، ملاحظة، نقل حظيرة، تحديد الغرض جماعياً (تربية/تسمين/بيع)، بيع، نفوق، مرض، خطة علاج، عزل، سونار، أو 'استقبال دفعة جديدة' لتسجيل رؤوس جديدة) — تُطبَّق على كل الرؤوس المحددة دفعة وحدة.\n"
            "من نفس الشاشة زر 'متابعة الحجر الصحي' يوديك لتتبع مراحل دفعات الاستقبال."
        ),
        translations={
            "en": {
                "title": "How do I apply an action to several heads at once?",
                "body": (
                    "From the side menu open 'bulk action' (a separate screen from the regular 'animals' one) — check heads with ✓ (or filter by barn/species then select all), then pick the action from the list (weight, vaccination, note, barn transfer, setting purpose in bulk (breeding/fattening/sale), sale, death, disease, treatment plan, isolation, sonar, or 'receive a new batch' to log new heads) — applies to all selected heads at once.\n"
                    "From the same screen the 'quarantine tracking' button takes you to track the stages of received batches."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_bulk_fattening_group",
        title="كيف أحدد غرض مجموعة حيوانات (تسمين/تربية/بيع)؟",
        keywords=[
            "اسمن مجموعة", "تسمين مجموعة", "تسمين دفعة", "غرض تسمين جماعي",
            "تربية مجموعة", "غرض تربية جماعي", "بيع سريع مجموعة", "غرض بيع جماعي", "تحديد الغرض جماعياً",
        ],
        body=(
            "من 'الإجراء الجماعي' أشّر الرؤوس اللي تبي (فلترة بحظيرة تسهّلها لو كلها بحظيرة وحدة)، بعدها اختر 'تحديد الغرض جماعياً' من قائمة الإجراءات واختر الغرض المطلوب (تسمين/تربية/بيع سريع) — يتحدد لكل الرؤوس المحددة دفعة وحدة، نفس الإجراء لأي غرض من الثلاثة.\n"
            "بعدها تلقاهم بالتبويب المطابق (التسمين/دافع/غير دافع...) بشاشة 'الحيوانات' (فلتر عرض بس، مو مكان تضيف فيه — الإضافة تصير بتحديد الغرض زي فوق). الغرض 'تسمين' تحديداً هو نفسه اللي يحدد هدف التغذية (بروتين/طاقة أعلى) لحساب خلطة العلف التلقائي لو حظيرتهم عندها مواعيد وجبات مجدولة."
        ),
        translations={
            "en": {
                "title": "How do I set the purpose of a group of animals (fattening/breeding/sale)?",
                "body": (
                    "From 'bulk action' check the heads you want (filtering by barn makes it easier if they're all in one barn), then pick 'set purpose in bulk' from the actions list and choose the purpose (fattening/breeding/quick sale) — it's set for all selected heads at once, the same action for any of the three purposes.\n"
                    "You'll then find them under the matching tab (fattening/breeding.../not breeding...) on the 'animals' screen (a display filter only, not where you add them — adding happens by setting the purpose as above). The 'fattening' purpose specifically is what sets the feeding target (higher protein/energy) for the automatic feed mix calculation if their barn has scheduled meal times."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_smart_sale_screen",
        title="كيف أستخدم شاشة البيع الذكي عملياً؟",
        keywords=["شاشة البيع الذكي", "استخدام البيع الذكي", "قائمة التوصيات"],
        body=(
            "من 'الحيوانات' ← 'البيع الذكي' (/animals/smart-sale) تلقى قائمة مرتّبة تلقائياً حسب إلحاح البيع — كل رأس له درجة وتفسير واضح ليش ترشّح. اضغط على أي رأس يوديك مباشرة لصفحته لتنفيذ البيع أو مراجعة التفاصيل قبل القرار."
        ),
        translations={
            "en": {
                "title": "How do I use the smart sale screen in practice?",
                "body": (
                    "From 'Animals' → 'Smart sale' (/animals/smart-sale) you get a list sorted automatically by sale urgency — each head has a score and a clear explanation of why it was suggested. Clicking any head takes you straight to its page to carry out the sale or review the details before deciding."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_milk_record",
        title="كيف أسجّل إنتاج الحليب؟",
        keywords=["تسجيل حليب", "انتاج الحليب", "اضافة حليب", "كمية حليب"],
        body=(
            "من صفحة الحيوان نفسه ← تبويب 'الحليب' ← '+ تسجيل جديد': حدد الكمية باللتر والفترة (صباح/مساء). السجلات التراكمية تظهر بتقرير الإنتاج، وتساعد على رصد أي تراجع مفاجئ مؤشراً مبكراً لمشكلة صحية."
        ),
        translations={
            "en": {
                "title": "How do I log milk production?",
                "body": (
                    "From the animal's own page → 'milk' tab → '+ New record': set the amount in liters and the period (morning/evening). Cumulative records show on the production report, and help spot any sudden drop as an early sign of a health problem."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_sale_invoice",
        title="كيف أطبع فاتورة بيع؟",
        keywords=["طباعة فاتورة", "فاتورة بيع", "فاتورة pdf"],
        body=(
            "بعد إتمام عملية البيع من صفحة الحيوان، زر 'فاتورة البيع' يولّد PDF جاهز للطباعة برأس فاتورة يحمل بيانات مزرعتك (الاسم/الجوال/العنوان المضبوطة بالإعدادات ← 'بيانات المزرعة')."
        ),
        translations={
            "en": {
                "title": "How do I print a sale invoice?",
                "body": (
                    "After completing a sale from the animal's page, the 'sale invoice' button generates a print-ready PDF with an invoice header carrying your farm's details (name/phone/address set in Settings → 'farm details')."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_species_breed_color",
        title="كيف أضيف فصيلة/سلالة/لون جديد للقوائم؟",
        keywords=["اضافة سلالة", "اضافة فصيلة", "اضافة لون جديد", "سلالة جديدة بالقائمة", "اضيف سلالة", "سلالة جديدة"],
        body=(
            "بفورم 'حيوان جديد'، جنب حقول الفصيلة/السلالة/اللون فيه زر '+ إضافة' صغير يفتح فورماً مصغّراً لإضافة قيمة جديدة للقائمة فوراً، بدون ما تحتاج تخرج من شاشة تسجيل الحيوان أصلاً."
        ),
        translations={
            "en": {
                "title": "How do I add a new species/breed/color to the lists?",
                "body": (
                    "On the 'new animal' form, next to the species/breed/color fields there's a small '+ Add' button that opens a mini form to add a new value to the list instantly, without needing to leave the animal registration screen at all."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_doctor_management",
        title="كيف أضيف طبيباً (خارجياً أو غير مسجَّل كمستخدم)؟",
        keywords=["اضافة طبيب", "قائمة الاطباء", "طبيب جديد بالقائمة", "اضيف طبيب", "طبيب جديد"],
        body=(
            "'الصحة' ← 'الأطباء' ← '+ طبيب جديد' — سجل مرجعي منفصل عن حسابات المستخدمين (`User`)، يُستخدم لتوثيق مين باشر كل زيارة بيطرية، حتى لو الطبيب نفسه ما له حساب دخول للنظام (طبيب زائر مثلاً)."
        ),
        translations={
            "en": {
                "title": "How do I add a doctor (external or not registered as a user)?",
                "body": (
                    "'Health' → 'Doctors' → '+ New doctor' — a reference record separate from user accounts (`User`), used to document who carried out each vet visit, even if the doctor themselves has no login account on the system (a visiting vet, for example)."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_create_protocol",
        title="كيف أنشئ بروتوكول علاج جديد (خطواته)؟",
        keywords=["انشاء بروتوكول", "بروتوكول جديد", "خطوات بروتوكول", "انشئ بروتوكول"],
        body=(
            "'الصحة' ← 'البروتوكولات' ← '+ بروتوكول جديد': أضف اسم البروتوكول ثم خطواته بالترتيب (كل خطوة نوعها ووصفها والفاصل الزمني عن الخطوة السابقة). بعد الحفظ، يصير جاهزاً تطبّقه على أي رأس بضغطة وحدة ('كيف أطبّق بروتوكول علاج جاهز؟')."
        ),
        translations={
            "en": {
                "title": "How do I create a new treatment protocol (its steps)?",
                "body": (
                    "'Health' → 'Protocols' → '+ New protocol': add the protocol's name then its steps in order (each step's type, description, and the time gap from the previous step). After saving, it's ready to apply to any head in one click ('How do I apply a ready treatment protocol?')."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_report_lifecycle",
        title="كيف يتحرّك البلاغ بعد ما يرفعه العامل؟",
        keywords=["دورة حياة البلاغ", "استلام بلاغ", "تحويل بلاغ", "اغلاق بلاغ", "يتحرك البلاغ", "بعد ما يرفعه العامل"],
        body=(
            "من شاشة 'البلاغات': استلام البلاغ (يبدأ المعالجة) → تنفيذ أو تحويل لشخص ثاني لو يحتاج تخصص مختلف → إغلاق نهائي بملاحظة. تقدر أيضاً تؤجّله أو تلغيه بسبب واضح بأي مرحلة قبل الإغلاق."
        ),
        translations={
            "en": {
                "title": "How does a report move after a worker files it?",
                "body": (
                    "From the 'reports' screen: receive the report (starts handling it) → execute or transfer it to someone else if it needs a different specialty → final close with a note. You can also postpone or cancel it with a clear reason at any stage before closing."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_fcr_calculator",
        title="كيف أحسب معدل التحويل الغذائي (FCR)؟",
        keywords=["حساب fcr", "معدل التحويل الغذائي", "كفاءة العلف"],
        body=(
            "'العلف' ← 'FCR': اختر الحظيرة والفترة الزمنية — النظام يحسب تلقائياً (كمية العلف المستهلكة ÷ الزيادة بالوزن) من سجلات حركة العلف وأوزان الحيوانات الفعلية المسجَّلة أصلاً، بدون أي إدخال إضافي منك."
        ),
        translations={
            "en": {
                "title": "How do I compute feed conversion ratio (FCR)?",
                "body": (
                    "'Feed' → 'FCR': pick the barn and the time period — the system computes it automatically (feed consumed ÷ weight gained) from feed movement records and actual logged animal weights, with no extra input from you."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_twin_estrus_program",
        title="كيف أدير برنامج شياع توأمي؟",
        keywords=["برنامج شياع توأمي", "اسفنجة", "مزامنة شياع"],
        body=(
            "'التكاثر' ← 'برامج الشياع' ← '+ برنامج جديد': أضف الإناث المشمولات، سجّل تركيب الإسفنجة وإزالتها وحقن الهرمونات بتواريخها — النظام يذكّرك تلقائياً بمواعيد كل خطوة (دخول الفحل بعد إزالة الإسفنجة بالمدة المضبوطة بالإعدادات)."
        ),
        translations={
            "en": {
                "title": "How do I manage a twin-estrus synchronization program?",
                "body": (
                    "'Breeding' → 'Estrus programs' → '+ New program': add the included females, log sponge insertion and removal and hormone injections with their dates — the system automatically reminds you of each step's timing (introducing the sire after sponge removal, per the interval set in settings)."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_monthly_cost_report",
        title="كيف أشوف تكلفة الرأس الشهرية؟",
        keywords=["تكلفة الشهر", "تقرير التكلفة الشهري", "مصاريف الشهر", "تكلفة الرأس الشهرية", "كم يكلفني كل رأس"],
        body=(
            "'المالية' ← 'تقرير تكلفة الرأس الشهرية' — يقسم مجموع مصاريف كل شهر (شراء + مصروف) على عدد رؤوسك **الفعلي بذلك الشهر بالذات** (يُحسب من تاريخ دخول/خروج كل رأس فعلياً — مو عدد رؤوسك اليوم)، عشان الأشهر الماضية ما تطلع بأرقام غلط لو تغيّر حجم قطيعك من وقتها. الإجمالي السنوي (آخر N شهر) يستخدم متوسط عدد الرؤوس عبر الفترة."
        ),
        translations={
            "en": {
                "title": "How do I see the monthly per-head cost?",
                "body": (
                    "'Finance' → 'Monthly per-head cost report' — divides each month's total expenses (purchases + expenses) by your **actual head count in that specific month** (computed from each head's real entry/exit date — not today's head count), so past months don't show wrong figures if your herd size changed since then. The yearly total (last N months) uses the average head count over the period."
                ),
            },
        },
    ),

    # ---------- توسعة ثالثة لمرشد الاستخدام (بند إضافي 117) ----------
    KBEntry(
        code="howto_bulk_purchase_intake",
        title="كيف أستقبل عدة رؤوس مشتراة دفعة وحدة (بدون دفعة رسمية)؟",
        keywords=["شراء جماعي رؤوس", "استقبال شراء متعدد", "تسجيل عدة رؤوس دفعة", "دفعة وحدة", "شراء جماعي"],
        body=(
            "'الحيوانات' ← 'شراء جماعي' (/animals/bulk-purchase): سجّل عدد الرؤوس المشتراة بنفس الصفقة بفورم واحد سريع (بدل تكرار فورم 'حيوان جديد' لكل رأس) — كل رأس ياخذ رقمه المستقل تلقائياً، وتقدر تعدّل تفاصيل أي رأس لاحقاً من صفحته."
        ),
        translations={
            "en": {
                "title": "How do I receive several purchased heads at once (without a formal batch)?",
                "body": (
                    "'Animals' → 'Bulk purchase' (/animals/bulk-purchase): log the number of heads bought in the same deal on one quick form (instead of repeating the 'new animal' form for each head) — each head gets its own number automatically, and you can edit any head's details later from its page."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_pharmacy_shortages",
        title="كيف أشوف نواقص الصيدلية؟",
        keywords=["نواقص الصيدلية", "نقص دواء", "مخزون دواء منخفض"],
        body=(
            "'الصحة' ← 'الصيدلية' ← 'نواقص الصيدلية' — قائمة تلقائية لكل دواء وصل مخزونه للحد الأدنى المضبوط له أو أقل (`min_stock_qty` بفورم كل دواء) — عرض حي، بدون أي إدخال يدوي."
        ),
        translations={
            "en": {
                "title": "How do I see pharmacy shortages?",
                "body": (
                    "'Health' → 'Pharmacy' → 'Pharmacy shortages' — an automatic list of every medicine whose stock has hit its set minimum or below (`min_stock_qty` on each medicine's form) — a live view, no manual entry."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_injection_guide",
        title="وين ألقى دليل طرق الحقن؟",
        keywords=["دليل الحقن", "طريقة الحقن", "طرق الحقن"],
        body=(
            "'الصحة' ← 'دليل الحقن' — مرجع عام يشرح الفرق بين طرق الحقن الشائعة (عضل/وريد/تحت الجلد) ومتى تُستخدم كل وحدة — إرشاد عام بس، اختيار الطريقة الفعلية لكل دواء قرار الطبيب."
        ),
        translations={
            "en": {
                "title": "Where do I find the injection methods guide?",
                "body": (
                    "'Health' → 'Injection guide' — a general reference explaining the difference between common injection routes (intramuscular/intravenous/subcutaneous) and when each one is used — general guidance only, the actual route for each medicine is the vet's decision."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_service_toggles",
        title="كيف أفعّل أو أوقف خدمة اختيارية بالنظام؟",
        keywords=["تفعيل خدمة", "ايقاف خدمة", "خدمات اختيارية", "تشغيل ميزة جديدة", "افعل خدمة", "خدمة اختيارية"],
        body=(
            "من الإعدادات ← قسم 'الخدمات' — قائمة خدمات اختيارية (تعدد الفروع، إدارة العملاء، لغات إضافية للعمال...) كل وحدة لها مفتاح تشغيل/إيقاف. الخدمة الموقوفة تختفي تماماً من كل واجهات النظام — فعّل بس اللي تحتاجه فعلياً."
        ),
        translations={
            "en": {
                "title": "How do I turn an optional service on or off?",
                "body": (
                    "From Settings → the 'services' section — a list of optional services (multiple branches, customer management, extra worker languages...) each with an on/off switch. A disabled service disappears completely from every interface in the system — only turn on what you actually need."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_new_warehouse",
        title="كيف أنشئ مستودعاً جديداً (فرع ثاني)؟",
        keywords=["مستودع جديد", "انشاء مستودع", "فرع تخزين ثاني", "انشئ مستودع"],
        body=(
            "'المستودعات' ← '+ مستودع جديد': سمّه (مثلاً 'مستودع الفرع الثاني') واحفظ. بعدها تقدر تحوّل كميات علف/دواء له من المستودع الرئيسي (راجع 'كيف أحوّل مخزون بين مستودعين؟')."
        ),
        translations={
            "en": {
                "title": "How do I create a new warehouse (a second branch)?",
                "body": (
                    "'Warehouses' → '+ New warehouse': name it (e.g. 'second branch warehouse') and save. Then you can transfer feed/medicine quantities to it from the main warehouse (see 'How do I transfer stock between two warehouses?')."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_manage_vaccination_schedule_entry",
        title="كيف ألغي أو أُنهي جدولة تحصين جماعي؟",
        keywords=["الغاء جدولة تحصين", "انهاء جدولة تحصين", "تعديل موعد تحصين جماعي", "الغي جدولة", "جدولة تحصين جماعي"],
        body=(
            "من 'تقويم التحصينات'، كل جدولة قادمة معها زرّين: 'إلغاء' (لو تراجعت عن الخطة) و'تم التنفيذ' (بعد ما تسجّل التحصينات الفعلية لكل رأس بالحظيرة عبر التحصين الجماعي أو الفردي) — يقفل الجدولة رسمياً بدل ما تبقى معلَّقة بلا نهاية."
        ),
        translations={
            "en": {
                "title": "How do I cancel or close a group vaccination schedule?",
                "body": (
                    "From 'vaccination calendar', every upcoming schedule has two buttons: 'cancel' (if you dropped the plan) and 'done' (after you've logged the actual vaccinations for each head in the barn via group or individual vaccination) — closes the schedule formally instead of leaving it pending forever."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_disease_drug_admin_lists",
        title="كيف أضيف نوع مرض جديد أو دواء لقائمة الأدوية المرجعية؟",
        keywords=["اضافة نوع مرض", "قائمة الادوية المرجعية", "دليل الادوية", "اضافة اسم دواء جديد", "اضيف نوع مرض", "نوع مرض جديد"],
        body=(
            "'الصحة' ← 'أنواع الأمراض' ← '+ إضافة' لقائمة أسماء الأمراض الشائعة (تسريع الإدخال بس، بدون علاج أو جرعة).\n"
            "'الصحة' ← 'دليل الأدوية' ← '+ إضافة' لإضافة اسم دواء جديد لقائمة الاختيار السريع وقت تسجيل مرض/زيارة/تحصين — منفصل عن 'دواء جديد' بالصيدلية (هذا مرجع أسماء بس، ذاك مخزون فعلي)."
        ),
        translations={
            "en": {
                "title": "How do I add a new disease type or medicine to the reference list?",
                "body": (
                    "'Health' → 'Disease types' → '+ Add' for the common disease names list (speeds up entry only, no treatment or dose).\n"
                    "'Health' → 'Drug catalog' → '+ Add' to add a new medicine name to the quick-pick list when logging a disease/visit/vaccination — separate from 'new medicine' in the pharmacy (this is a names reference only, that's actual stock)."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_finance_health_view",
        title="كيف أشوف المالية المرتبطة بالصحة فقط؟",
        keywords=["مالية الصحة", "تكلفة العلاج المالية", "مصاريف الصحة فقط"],
        body=(
            "'المالية' ← 'مالية الصحة' (شاشة منفصلة عن المالية الكاملة) — تعرض بس المصاريف المرتبطة بعلاج/دواء/تحصين، مفيدة لدور 'الدكتور' اللي عنده صلاحية يشوف تكلفة العلاج بدون الاطلاع على كامل الحسابات المالية للمزرعة."
        ),
        translations={
            "en": {
                "title": "How do I see finances linked to health only?",
                "body": (
                    "'Finance' → 'Health finance' (a screen separate from full finance) — shows only expenses linked to treatment/medicine/vaccination, useful for the 'doctor' role who has permission to see treatment cost without access to the farm's full financial accounts."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_edit_team_member",
        title="كيف أعطّل حساب عضو فريق (بدون حذفه)؟",
        keywords=["تعطيل حساب عضو", "ايقاف حساب موظف", "تعطيل عامل", "اعطل حساب", "حساب عضو فريق"],
        body=(
            "من 'أعضاء الفريق'، جنب كل عضو زر تبديل الحالة (نشط/معطَّل) — تعطيل الحساب يمنعه من تسجيل الدخول فوراً بدون حذف أي بيانات أو سجل تاريخي مرتبط فيه (مهام أنجزها، بلاغات رفعها...)."
        ),
        translations={
            "en": {
                "title": "How do I deactivate a team member's account (without deleting it)?",
                "body": (
                    "From 'team members', next to each member is a status toggle button (active/disabled) — disabling the account blocks them from logging in immediately without deleting any of their data or history (tasks they completed, reports they filed...)."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_animal_workflow_plan",
        title="كيف أشوف أو أعدّل خطة دورة إنتاج رأس معيّن؟",
        keywords=["خطة دورة الانتاج", "مراحل الحيوان", "تعديل خطة الرأس", "خطة دورة انتاج", "دورة انتاج راس"],
        body=(
            "من صفحة الحيوان ← تبويب 'دورة الإنتاج' — يعرض المرحلة الحالية تلقائياً (محسوبة من أدلة فعلية: تلقيح/تشخيص حمل/ولادة...، مو إدخالاً يدوياً)، والمسار المتوقع القادم. زر 'خطة' يخليك تسجّل نية مستقبلية (مثلاً 'تسمين' بدل 'إنتاج حليب') تؤثر على حساب المرحلة القادمة."
        ),
        translations={
            "en": {
                "title": "How do I view or edit a specific head's production cycle plan?",
                "body": (
                    "From the animal's page → 'production cycle' tab — shows the current stage automatically (computed from actual evidence: mating/pregnancy diagnosis/birth..., not manual entry), and the expected upcoming path. The 'plan' button lets you log a future intent (e.g. 'fattening' instead of 'milk production') that affects the next stage's calculation."
                ),
            },
        },
    ),

    # ---------- توسعة رابعة لمرشد الاستخدام (بند إضافي 118) ----------
    KBEntry(
        code="howto_incubator_management",
        title="كيف أضيف حاضنة جديدة وأربطها بالبيض؟",
        keywords=["اضافة حاضنة", "حاضنة جديدة", "ربط بيضة بحاضنة", "اضيف حاضنة"],
        body=(
            "'النعام' ← 'الحاضنات' ← '+ حاضنة جديدة': سمّها وسجّل سعتها. بعدها من شاشة أي بيضة، زر 'وضع بالحاضنة' يربطها بحاضنة موجودة — تقدر تشوف كل البيض داخل حاضنة معيّنة من صفحتها."
        ),
        translations={
            "en": {
                "title": "How do I add a new incubator and link it to eggs?",
                "body": (
                    "'Ostrich' → 'Incubators' → '+ New incubator': name it and log its capacity. Then from any egg's screen, the 'place in incubator' button links it to an existing incubator — you can see all eggs inside a specific incubator from its page."
                ),
            },
        },
    ),
    KBEntry(
        code="howto_offline_mode",
        title="هل التطبيق يشتغل بدون إنترنت؟",
        keywords=["العمل بدون انترنت", "اوفلاين", "بدون نت", "انقطع النت", "يشتغل بدون انترنت", "التطبيق بدون انترنت"],
        body=(
            "نعم — الشاشات الميدانية الأساسية (مهامي، البلاغات، تسجيل وزن...) تفتح وتسجّل بياناتك محلياً حتى لو النت مقطوع، وتُرفع تلقائياً لما يرجع الاتصال (زر 🔄 يظهر لو فيه بيانات بانتظار المزامنة). لو فورم معيّن رُفض من السيرفر وقت المزامنة (بيانات ناقصة مثلاً)، يطلب منك تراجعه وتعيد إدخاله يدوياً."
        ),
    ),
    KBEntry(
        code="howto_report_execute_vs_transfer",
        title="ما الفرق بين 'تنفيذ' و'تنفيذ ذاتي' و'تحويل' البلاغ؟",
        keywords=["فرق تنفيذ وتحويل البلاغ", "تنفيذ ذاتي بلاغ", "تحويل البلاغ لشخص ثاني", "تنفيذ وتحويل البلاغ", "الفرق بين تنفيذ"],
        body=(
            "من شاشة تفصيل البلاغ:\n"
            "• 'تنفيذ': الدكتور/المستلم ينفّذ الإجراء المطلوب بنفسه ويوثّقه.\n"
            "• 'تنفيذ ذاتي': يسمح للعامل نفسه اللي رفع البلاغ يوثّق إنه نفّذ إجراء بسيط بنفسه (لو الصلاحية تسمح)، بدون انتظار الدكتور.\n"
            "• 'تحويل': يمرّر البلاغ لشخص ثاني (تخصص مختلف) بدل ما ينفّذه المستلم الحالي."
        ),
    ),
    KBEntry(
        code="howto_remove_repro_device",
        title="كيف أسجّل إزالة إسفنجة/جهاز تكاثر؟",
        keywords=["ازالة اسفنجة", "ازالة جهاز تكاثر", "اخراج الاسفنجة"],
        body=(
            "من صفحة برنامج الشياع التوأمي ← جدول الأجهزة المركَّبة، زر 'إزالة' جنب أي جهاز — يسجّل تاريخ ووقت الإزالة، ويبدأ تلقائياً عدّ موعد دخول الفحل المتوقع (حسب المدة المضبوطة بالإعدادات)."
        ),
    ),
    KBEntry(
        code="howto_animal_quick_info",
        title="وش يعرض 'معلومات سريعة' لما أمرّر على رقم رأس؟",
        keywords=["معلومات سريعة", "quick info", "تلميح الحيوان"],
        body=(
            "بشاشات فيها إشارة لرقم رأس (مثلاً بشاشة التحصين الجماعي)، تمرير المؤشر أو الضغط على رقمه يفتح بطاقة معلومات سريعة (العمر، الوزن الحالي، الحظيرة، الحالة) بدون ما تحتاج تفتح صفحته الكاملة."
        ),
    ),
    KBEntry(
        code="howto_mortality_births_reports",
        title="كيف أفهم تقريري النفوق والولادات؟",
        keywords=["تقرير النفوق", "تقرير الولادات", "فهم تقرير النفوق"],
        body=(
            "'التقارير' ← 'النفوق': يلخّص عدد حالات النفوق بالفترة المختارة مع توزيع الأسباب — مؤشر مبكر لو صنف/حظيرة معيّنة فيها تكرار غير طبيعي.\n"
            "'التقارير' ← 'الولادات': يلخّص عدد الولادات، نسبة التوائم، ووزن المواليد — أساس تقييم أداء التكاثر بالمزرعة عبر الوقت."
        ),
    ),
    KBEntry(
        code="howto_equipment_add",
        title="كيف أضيف معدة جديدة للمزرعة؟",
        keywords=["اضافة معده", "معده جديده", "صنف معدات جديد"],
        body=(
            "'المعدات' ← 'إضافة صنف' — اكتب الاسم والفئة والوحدة (قطعة افتراضياً)، وممكن تحدد رصيد بداية وحد أدنى للمخزون يظهرك تنبيه لو نزل تحته. بعدها تقدر تسجّل حركات صرف/استرجاع/استعارة على هذا الصنف من صفحته."
        ),
    ),
    KBEntry(
        code="howto_equipment_movement",
        title="كيف أسجّل صرف أو استعارة أو استرجاع معدة؟",
        keywords=["استعاره معده", "استرجاع معده", "صرف معده", "حركة معدات"],
        body=(
            "من صفحة الصنف بالمعدات ← 'تسجيل حركة': اختر 'وارد' أو 'صادر'، الكمية، والحظيرة لو تتعلق بحظيرة معيّنة. لو الصادر استعارة أداة هترجع (مو صرف نهائي)، حدد اسم العامل المستلم — الكمية تُخصم من الرصيد فوراً، وترجع تلقائياً لما تضغط 'استرجاع' جنب نفس الحركة بعدين. صفحة الصنف تعرض قائمة القطع المستعارة اللي لسا ما رجعت."
        ),
    ),
    KBEntry(
        code="howto_barn_management",
        title="كيف أضيف حظيرة جديدة أو أعدّل بياناتها؟",
        keywords=["اضافة حظيره", "حظيره جديده", "تعديل حظيره", "تغيير العامل المسؤول"],
        body=(
            "'الحظائر' ← 'إضافة حظيرة': رقم الحظيرة (لازم يكون فريد)، الاسم، النوع (عادية/عزل/نفاس/نمو/حامل - الشهور الأخيرة/رضاعة/عام)، السعة، والعامل المسؤول عنها. تحديد 'حامل - الشهور الأخيرة' أو 'رضاعة' يفعّل فحصاً تلقائياً ينبّهك وينقل أي رأس وصل هذي الحالة فعلياً لو كان بحظيرة ثانية.\n"
            "من نفس الشاشة أضف مواعيد وجبات العلف اليومية للحظيرة — كل موعد يولّد تلقائياً مهمة توزيع علف (بكمية محسوبة تلقائياً من المخزون الفعلي) للعامل المسؤول.\n"
            "أهم استخدام عملي ثانٍ لشاشة 'تعديل' هو تغيير العامل المسؤول بعدين، لأنه أساس توجيه المهام التلقائي والتنبيهات لذاك العامل."
        ),
    ),
    KBEntry(
        code="howto_feeding_schedule",
        title="كيف أجدول مواعيد وجبات العلف تلقائياً؟",
        keywords=[
            "جدول وجبات علف", "مواعيد وجبات", "توزيع علف تلقائي", "كم مره اعلف", "وجبة علف",
            "اضافة موعد وجبة", "اضيف موعد وجبة", "كيف اضيف موعد وجبه", "موعد وجبه جديد",
        ],
        body=(
            "من 'تعديل حظيرة' أضف موعد وجبة واحد أو أكثر (وقت باليوم) — إعداد مستقل لكل حظيرة.\n"
            "عند وصول الموعد، يتولّد تلقائياً مهمة 'وجبة علف' للعامل المسؤول عن الحظيرة، فيها خلطة اليوم المحسوبة تلقائياً من المخزون الفعلي (كمية وتكلفة كل مكوّن). لما يضغط العامل 'تم الإنجاز' بعد التوزيع الفعلي، يُخصَم المخزون تلقائياً."
        ),
    ),
    KBEntry(
        code="howto_barn_physiology_sort",
        title="كيف أفرز الحظائر حسب حالة الحيوانات (حمل متأخر/رضاعة)؟",
        keywords=["فرز حظائر", "حظيرة حوامل", "حظيرة رضاعة", "نقل تلقائي حظيرة", "حمل متأخر"],
        body=(
            "حدد نوع الحظيرة 'حامل - الشهور الأخيرة' أو 'رضاعة' من شاشة تعديل الحظيرة. أي رأس وصل هذي الحالة فعلياً (حمل بمرحلته المتأخرة، أو أم عندها مولود عمره أقل من 90 يوم) وحظيرته الحالية مو مطابقة، يتولّد له تلقائياً مهمة مقترحة تنقله — تحتاج اعتماد الدكتور، وإنجازها فعلياً ينقل الرأس."
        ),
    ),
    KBEntry(
        code="howto_pharmacy_purchase",
        title="كيف أسجّل عملية شراء دواء جديدة للصيدلية؟",
        keywords=["شراء دواء", "شراء دواء جديد", "تسجيل شراء دواء", "دفعة دواء جديده"],
        body=(
            "من صفحة تعديل الدواء بالصيدلية ← 'تسجيل شراء': أدخل الكمية، تاريخ الشراء، تاريخ انتهاء هذي الدفعة تحديداً (ممكن يختلف عن دفعات سابقة)، والسعر لو حبيت. الرصيد الإجمالي (`available_qty`) يزيد تلقائياً بنفس الكمية، وتقدر تراجع كل دفعات هذا الدواء وتواريخها من نفس الصفحة.\n"
            "**لو كتبت سعر الوحدة، تُنشأ تلقائياً عملية 'شراء' مالية حقيقية بفئة 'أدوية' تظهر بشاشة المالية** (يحتاج صلاحية إدارة المالية كمان لو فيه سعر) — بدون سعر، يُسجَّل بالمخزون بس. فورم 'تعديل' المباشر يبقى موجود لتصحيحات الرصيد العامة بس، مو بديل عن تسجيل الشراء."
        ),
    ),
    KBEntry(
        code="howto_pharmacy_dose_table",
        title="كيف أضبط جدول الجرعة حسب العمر لدواء معيّن؟",
        keywords=["جدول الجرعه حسب العمر", "جرعه حسب العمر", "جرعه للدواء"],
        body=(
            "بفورم إضافة/تعديل الدواء بالصيدلية، فيه جدول 'الجرعة حسب العمر' — تضيف صفوف (من عمر — إلى عمر — الجرعة بالمل)، ويُستخدم تلقائياً بشاشة التحصين الجماعي لاقتراح جرعة كل رأس حسب عمره. الجدول يُستبدل بالكامل عند كل حفظ (يمسح القديم ويكتب الجديد) — تذكّر إن هذا اقتراح تشغيلي، والجرعة النهائية قرار الدكتور دايماً."
        ),
    ),
    KBEntry(
        code="howto_usage_drug_catalog",
        title="كيف أضيف طريقة استخدام أو اسم دواء جديد لقوائم الاختيار؟",
        keywords=["طريقة استخدام جديده", "اضافة اسم دواء", "كتالوج الادويه"],
        body=(
            "من فورم 'دواء جديد' بالصيدلية، جنب حقل 'طريقة الاستخدام' وحقل 'اسم الدواء' فيه رابط 'إضافة جديد' يفتح فورم بسيط (اسم بس، أو اسم + فئة الدواء للكتالوج). القائمتين مستقلتين عن أصناف الصيدلية الفعلية — مجرد قوائم اقتراح تسهّل تعبئة الفورم لاحقاً، بدون تكرار كتابة."
        ),
    ),
    KBEntry(
        code="howto_repro_program_status",
        title="كيف أغيّر حالة برنامج الشياع التوأمي؟",
        keywords=["حالة برنامج التزامن", "تغيير حالة البرنامج", "حاله برنامج الشياع"],
        body=(
            "من صفحة تفاصيل برنامج الشياع التوأمي فيه زر لتغيير حالة البرنامج (مثلاً من نشط لمكتمل أو ملغى) — التغيير يُسجَّل بسجل الأحداث تلقائياً."
        ),
    ),
    KBEntry(
        code="howto_pregnancy_abort",
        title="كيف أسجّل إجهاض حيوان حامل؟",
        keywords=["تسجيل اجهاض", "اجهاض حيوان", "اجهاض حمل"],
        body=(
            "من صفحة الحمل ← زر 'تسجيل إجهاض' (متاح مرة وحدة بس لكل حمل، ما يقبل تكرار). النظام يطبّق تلقائياً بروتوكول عزل: عزل الحيوان فوراً + مهمة سحب عيّنات + مراقبة حرارة لبقية حظيرة الدفعة لعدة أيام — عشان أي سبب معدي محتمل يُكتشف بدري."
        ),
    ),
    KBEntry(
        code="howto_feed_movements",
        title="كيف أسجّل حركة صرف علف؟",
        keywords=["حركة صرف علف", "صرف علف", "تسجيل صرف علف", "حركة مخزون علف"],
        body=(
            "'العلف' ← 'حركة المخزون' ← 'تسجيل حركة': اختر الصنف، نوع الحركة (وارد/صادر)، الكمية، والحظيرة أو الرأس المرتبط لو ينطبق. كل حركة تُسجَّل بتاريخها وتُحدّث الرصيد الإجمالي فوراً — أساس تقارير معدل التحويل الغذائي (FCR) والتكلفة الشهرية."
        ),
    ),
    KBEntry(
        code="howto_feed_barn_plans",
        title="كيف أحدد خطة تغذية لحظيرة؟",
        keywords=["خطة تغذيه لحظيره", "تغذيه لحظيره", "خطة علف حظيره", "اضافة خطة تغذيه"],
        body=(
            "'العلف' ← 'خطط الحظائر' ← 'إضافة خطة': اختر الحظيرة، الوصفة (الخلطة)، الكمية اليومية لكل رأس، وتاريخ البداية. لو رفعت نسبة المركّز فجأة عن آخر خطة بشكل كبير، النظام يحذّرك ويطلب سبب تجاوز صريح قبل الحفظ — احتياط ضد تحميص الكرش من تغيير مفاجئ."
        ),
    ),
    KBEntry(
        code="howto_feed_calculator",
        title="وش الفرق بين حاسبة العلف وموازِن العليقة؟",
        keywords=["حاسبة العلف", "حاسبة الاحتياج اليومي", "فرق حاسبة الموازن"],
        body=(
            "'العلف' ← 'حاسبة الاحتياج': تدخل رأس أو وزن يدوي، ترجع لك الاحتياج اليومي مع اقتراح أقرب وصفات (خلطات) جاهزة مطابقة له.\n"
            "'موازِن العليقة' (Optimizer): نفس حساب الاحتياج، بس بدل اقتراح وصفة جاهزة يبني لك خلطة تلقائية من أصناف العلف المتوفرة فعلياً بمخزونك حالياً — أنسب لما ما عندك وصفة جاهزة تناسب الاحتياج."
        ),
    ),
    KBEntry(
        code="howto_batch_hold_catchup",
        title="كيف أستبعد رأس من تقدّم الدفعة أو ألحقه بها لاحقاً؟",
        keywords=["استبعاد راس من الدفعه", "راس متاخر", "الحاق راس متاخر", "تحرير استبعاد", "catch up دفعه"],
        body=(
            "من صفحة تفاصيل الدفعة، جنب أي رأس: زر 'استبعاد' (Hold) يوقفه مؤقتاً عن التقدّم الجماعي التالي (مثلاً لو مريض أو وزنه ما يوافق) مع كتابة السبب — وزر 'تحرير' يرجّعه للتقدّم العادي بعدين.\n"
            "لو رأس فاته تقدّم كامل وتأخر عن بقية دفعته، زر 'إلحاق متأخر' (Catch-up) يقدّمه لنفس مرحلة الدفعة الحالية دفعة وحدة، مع تحديد حظيرته الجديدة لو لزم — يحتاج صلاحية اعتماد البوابات."
        ),
    ),
    KBEntry(
        code="vaccination_schedule_reference",
        title="جدول تحصين الأغنام/الماعز المرجعي (بند إضافي 290)",
        keywords=["جدول تحصين الاغنام", "جدول تحصين الماعز", "متى احصن اغنامي", "شنو جدول التحصين", "تحصين اغنام جديدة"],
        body=(
            "مرجع عام من مصادر بيطرية وتقارير محلية (راجع دكتورك البيطري قبل أي تطبيق فعلي — هذا مو تشخيص أو جرعة، مبادئ عامة بس):\n\n"
            "**CDT (تسمم دموي معوي + كزاز)** — اللقاح شبه المتفق عليه عالمياً لكل الأغنام/الماعز. الحملان: أول جرعة عمر 4-8 أسابيع + معززة بعد 3-4 أسابيع، ثم سنوياً. النعاج الحوامل: قبل الولادة بـ4-6 أسابيع.\n"
            "**طاعون المجترات الصغيرة (PPR) + جدري الأغنام** — متوطّنان بالسعودية (أعلى انتشار لـPPR سُجّل بمنطقة الرياض 86% بدراسة مسحية). لقاح مشترك يعطي حماية 12 شهر، عادة بفصل الربيع.\n"
            "**الحمى القلاعية (FMD)** — متوطّنة وشديدة العدوى. **إلزامية لأي رأس مستورد/مشترى جديد أثناء الحجر الصحي** قبل الاختلاط بالقطيع، خصوصاً لو حالته التحصينية غير معروفة.\n\n"
            "الثلاثة مسجَّلة كأصناف مرجعية جاهزة بالصيدلية (بدون جرعة أو سعر مفروضين) — راجعها من 'الصحة' ← 'الصيدلية'، وعبّي الجرعة والسعر الحقيقيين لما تستقبل المنتج الفعلي. تقدر بعدها تربطها بمهمتي 'رش وقائي'/'تحصين مبدئي' التلقائيتين عند شراء رأس جديد (الإعدادات ← 'دواء استقبال الرأس الجديد'، بند 283)."
        ),
    ),
    KBEntry(
        code="howto_task_daily_templates",
        title="كيف أضيف مهمة يومية متكررة تتوزع تلقائياً؟",
        keywords=["مهمة يوميه متكرره", "قالب مهمه يوميه", "مهام العامل التلقائيه"],
        body=(
            "'المهام' ← 'مهام العامل التلقائية' (يحتاج صلاحية تعيين مهام لأي عامل): 'إضافة' مهمة يومية (مثلاً تنظيف، سقاية، فحص يومي) — تتحول تلقائياً لمهام فعلية توصل للعامل المسؤول كل يوم، بدون انتظار اعتماد (خلافاً لبقية المهام التلقائية بالنظام). زر 'إيقاف/تفعيل' جنب كل قالب يوقفه مؤقتاً بدون حذفه."
        ),
    ),
    KBEntry(
        code="howto_task_lifecycle_active",
        title="كيف أؤجّل أو ألغي أو أسترجع مهمة فعلية موكَلة لعامل؟",
        keywords=["الغاء مهمه فعليه", "مهمه فعليه", "استرجاع مهمه محذوفه", "حذف مهمه نهائي", "تاجيل مهمه فعليه"],
        body=(
            "لمهمة موكَلة فعلياً لعامل (مو مقترحة بانتظار اعتماد): زر 'تأجيل' يؤجلها ليوم واحد من موعدها الحالي، وزر 'إلغاء' يلغيها. لو صاحب الحلال حذف مهمة اقترحها النظام، تنتقل لصندوق مراجعته — من هناك زر 'استرجاع' يرجّعها نشطة، وزر 'حذف نهائي' يمسحها فعلياً بلا رجعة."
        ),
    ),
    KBEntry(
        code="howto_suggested_tasks_window",
        title="ليش المهام المقترحة تطلع اليوم وبكرة بس، ووين راحت المهام القديمة؟",
        keywords=["المهام المقترحه اليوم فقط", "مهام مقترحه اختفت", "حذف تلقائي مهمه مقترحه", "مهام مقترحه قديمه", "نافذة المهام المقترحه"],
        body=(
            "جدول 'مهام مقترحة بانتظار الاعتماد' يعرض بس المهام اللي موعدها اليوم أو بكرة — عشان ما يتراكم عليك باكلوج ضخم بمهام قديمة تحتاج مراجعتك.\n"
            "لو مهمة مقترحة فات موعدها يومين كاملين بدون ما تعتمدها أو تؤجلها أو تحذفها يدوياً، النظام يحذفها تلقائياً (تنتقل لصندوق مراجعتك — نفس مصير الحذف اليدوي، مو حذف نهائي فوري، تقدر تسترجعها من هناك لو احتجت).\n"
            "المهام اللي بلا موعد محدد إطلاقاً (نادرة، زي بعض خطط العلاج المقترحة) تبقى تظهر دايماً بغض النظر عن هذي النافذة."
        ),
    ),
    KBEntry(
        code="howto_purchase_request_report",
        title="كيف أنشئ قائمة طلب شراء من التقارير؟",
        keywords=["قائمة طلب شراء", "طلب شراء", "تقرير طلب الشراء", "طلب شراء من التقارير"],
        body=(
            "'التقارير' ← 'طلب شراء' شاشة منفصلة تلخّص الأصناف اللي وصلت أو قربت من الحد الأدنى بالمخزون (علف/دواء/معدات) — أساس تجهيز قائمة شراء فعلية بدل مراجعة كل مخزون لحاله. لتصدير أي تقرير كملف، راجع تصدير التقارير العادي (زر 'تصدير Excel'/'تصدير PDF')."
        ),
    ),
    KBEntry(
        code="howto_climate_refresh",
        title="كيف أحدّث توقعات الطقس يدوياً؟",
        keywords=["تحديث توقعات الطقس", "توقعات الطقس", "تحديث الطقس يدوي", "تحديث رادار المناخ"],
        body=(
            "من شاشة 'رادار المناخ' زر 'تحديث الآن' يجلب توقعات طقس جديدة فوراً بدل انتظار التحديث التلقائي المجدول — مفيد لو غيّرت إحداثيات المزرعة بالإعدادات وتبي تتأكد من صحة القراءة الجديدة مباشرة."
        ),
    ),

    # ---------- الرواتب (بند إضافي 268 — قسم كامل، ما كان موجود بقاعدة المعرفة إطلاقاً) ----------

    KBEntry(
        code="howto_salary_setup",
        title="كيف أسجّل الراتب الأساسي وبيانات هوية عامل؟",
        keywords=["راتب اساسي", "اعداد الرواتب", "بيانات هوية العامل", "تسجيل راتب عامل", "الجنسية رقم الجواز"],
        body=(
            "'الفريق' ← 'إعداد الرواتب' — شاشة بيانات أساسية تُعبَّى مرة وحدة لكل عامل، تُستخدم تلقائياً بكل مسير راتب بعدها:\n"
            "• 'بيانات الراتب': الراتب الأساسي، طريقة الدفع (نقداً/تحويل بنكي)، وتاريخ الوصول للسعودية (اختياري — يُستخدم لحساب الراتب المتناسب، راجع بند تاريخ الوصول أدناه).\n"
            "• 'بيانات الهوية': الجنسية، رقم الجواز، رقم الحدود.\n"
            "• بطاقة منفصلة 'بيانات صاحب الحلال' بنفس الشاشة (اسمه، رقم هويته، رقم جواله) — تظهر تلقائياً كصاحب عمل بكل وصل راتب.\n"
            "صلاحية 'إدارة الرواتب' منفصلة عمداً عن صلاحية إدارة الفريق الكاملة — المحاسب يقدر يدخل هذي البيانات بدون ما يقدر يغيّر أدوار أو كلمات مرور."
        ),
    ),
    KBEntry(
        code="howto_payroll_prepare",
        title="كيف أجهّز راتب الشهر لعامل؟",
        keywords=["تجهيز راتب", "رواتب الشهر", "راتب هذا الشهر", "اعداد راتب شهري", "مسودة راتب"],
        body=(
            "'الفريق' ← 'رواتب الشهر' — قائمة كل الأعضاء لشهر/سنة محددة (افتراضياً الشهر الحالي). زر 'عرض/تجهيز' جنب أي عامل يفتح شاشة تجهيزه:\n"
            "• الراتب الأساسي يُعبَّى تلقائياً من 'إعداد الرواتب' (أو الراتب المتناسب لو مسجَّل تاريخ وصول أو فترة سفر — راجع البند المخصص).\n"
            "• أضف مكافأة (اختياري) واسم مستلم الحوالة (لو طريقة الدفع تحويل — يتغيّر كل شهر بشكل مستقل).\n"
            "• أضف خصومات بزر '+ إضافة خصم' (راجع بند الخصومات).\n"
            "• 'حفظ مسودة' يحفظ التعديلات بدون ترحيل مالي — تقدر ترجع تعدّلها لاحقاً. 'تأكيد نهائي' يرحّل المبلغ الصافي فعلياً لسجل المالية ويقفل التعديل عليه نهائياً."
        ),
    ),
    KBEntry(
        code="howto_payroll_confirm",
        title="ماذا يحصل بالضبط لما أأكّد راتب عامل نهائياً؟",
        keywords=["تأكيد راتب", "تأكيد نهائي للراتب", "ترحيل راتب", "اعتماد الراتب"],
        body=(
            "'تأكيد نهائي' بشاشة تجهيز الراتب يفعل شيئين معاً: (1) يرحّل الصافي المستحق كعملية مصروف حقيقية بسجل 'المالية' (يدخل بكل التقارير المبنية عليها: صافي الربح، تكلفة الرأس الشهرية، تشخيص الخسارة)، (2) يقفل الراتب من أي تعديل لاحق — يصير سجلاً ثابتاً (Snapshot) حتى لو تغيّر الراتب الأساسي للعامل لاحقاً. لو فيه خصومات، تطلع رسالة تأكيد إضافية توضح المبلغ والسبب قبل الترحيل النهائي — تقدر تراجع القرار قبل ما تضغط تأكيد."
        ),
    ),
    KBEntry(
        code="howto_payroll_deductions",
        title="كيف أضيف خصم على راتب عامل؟",
        keywords=["اضافة خصم", "خصم راتب", "خصومات متعددة", "خصم على العامل"],
        body=(
            "بشاشة 'تجهيز راتب'، زر '+ إضافة خصم' يضيف سطر جديد (المبلغ + سبب الخصم نصي حر) — تقدر تضيف عدد غير محدود من الخصومات، كل وحد بسببه المستقل. حفظ مسودة يستبدل كل الخصومات القديمة بالقائمة الجديدة كاملة (مو تعديل جزئي) — يعني لو حذفت سطر خصم وحفظت، ينحذف فعلاً. مجموع الخصومات يُطرح تلقائياً من (الأساسي + المكافأة) ليطلع الصافي المستحق."
        ),
    ),
    KBEntry(
        code="howto_payroll_receipt",
        title="كيف أطبع وصل الراتب أو أرفع نسخة موقَّعة منه؟",
        keywords=["طباعة وصل الراتب", "وصل موقع", "رفع وصل راتب", "مسير راتب pdf"],
        body=(
            "بعد تأكيد الراتب نهائياً، زر '🖨️ طباعة الوصل' (من 'رواتب الشهر' أو تفاصيل الراتب) يطلع مسير راتب PDF رسمي — بيانات صاحب الحلال، بيانات العامل (الاسم دايماً، الجنسية/الجواز لو مسجَّلين)، تفصيل الراتب والخصومات، وطريقة الدفع (لو تحويل، يوضّح 'من {صاحب الحلال} إلى {مستلم الحوالة}' صراحة).\n"
            "زر '📎 الوصل الموقَّع' يفتح صفحة مستقلة لرفع صورة أو PDF للوصل بعد ما يوقّعه العامل فعلياً على الورق — يُحفَظ ويظهر لاحقاً بشاشة 'تقارير الرواتب حسب العامل'."
        ),
    ),
    KBEntry(
        code="howto_payroll_reports",
        title="كيف أشوف تاريخ رواتب عامل معيّن أو إجمالي رواتب الشهر؟",
        keywords=["تقارير الرواتب", "تاريخ رواتب عامل", "اجمالي رواتب الشهر", "كم صرفنا رواتب"],
        body=(
            "'الفريق' ← 'رواتب الشهر' ← 'تقارير الرواتب حسب العامل':\n"
            "• بطاقة 'إجمالي رواتب الشهر' بالأعلى — مستقلة عن اختيار عامل معيّن، فلترة بسنة/شهر، تعطيك مجموع كل الرواتب المؤكَّدة لذلك الشهر لكل الفريق + تفصيل قابل للطي لكل عامل ومبلغه.\n"
            "• اختيار عامل معيّن يعرض كل رواتبه المؤكَّدة عبر كل الأشهر السابقة، مع رابط مباشر لوصله الموقَّع (لو مرفوع) لكل شهر."
        ),
    ),
    KBEntry(
        code="howto_worker_travel",
        title="عندي عامل مسافر، كيف أسجّله وكيف يأثر على راتبه؟",
        keywords=["عامل مسافر", "تسجيل سفر", "سفر عامل", "راتب اثناء السفر", "عودة من السفر"],
        body=(
            "'إعداد الرواتب' ← زر '🛫 تسجيل سفر' جنب اسم العامل — يسجّل بداية فترة سفر (يظهر شارة 'مسافر حالياً' جنب اسمه). لما يرجع، اضغط '🛬 تسجيل عودة' على نفس الزر.\n"
            "**الأثر على الراتب:** أيام السفر تُستبعد من حساب الراتب المتناسب لذلك الشهر (يتقسم على أيام الشهر الفعلية، مو تصفير الشهر كامل) — يظهر تلقائياً كقيمة مقترحة بشاشة 'تجهيز راتب' مع زر 'استخدم القيمة المقترحة'، يبقى قابل للتعديل اليدوي دايماً.\n"
            "لتصحيح تاريخ فترة سفر أو حذفها، زر '📋 سجل السفر' جنب كل عامل يفتح كل فترات سفره القديمة قابلة للتعديل/الحذف مباشرة، مع فورم لإضافة فترة بأثر رجعي لو نسيت تسجّلها وقتها."
        ),
    ),
    KBEntry(
        code="howto_saudi_arrival_date",
        title="ما فايدة 'تاريخ الوصول للسعودية' بالرواتب؟",
        keywords=["تاريخ الوصول للسعودية", "راتب اول شهر", "راتب متناسب", "عامل جديد راتب"],
        body=(
            "لو سجّلت تاريخ وصول عامل للسعودية بشاشة 'إعداد الرواتب'، النظام يحسب راتبه **كل شهر** (مو أول شهر بس) بالتناسب مع أيام حضوره الفعلية — لو دخل يوم 21 من شهر 30 يوم، أول راتب له يُحسب لـ10 أيام بس تلقائياً، ويظهر كقيمة مقترحة بشاشة تجهيز راتبه. عامل بدون تاريخ وصول مسجَّل = راتب كامل عادي بدون أي تناسب، بدون تغيير عن المعتاد."
        ),
    ),
    KBEntry(
        code="howto_top_performer_bonus",
        title="شنو معنى شارة 'أعلى نقطة أداء الشهر الماضي' بشاشة تجهيز الراتب؟",
        keywords=["اعلى نقطة اداء", "شارة اداء الراتب", "اقترح مكافأة", "موظف الشهر"],
        body=(
            "لو العامل اللي تجهّز راتبه كان صاحب أعلى نقطة أداء بتقرير أداء الفريق للشهر الماضي، تطلع شارة '🏆 أعلى نقطة أداء الشهر الماضي' فوق فورم تجهيز راتبه (بس وهو لسا مسودة، تختفي بعد التأكيد). زر 'اقترح مكافأة' جنبها بس يركّز حقل المكافأة عشان تكتب رقم بنفسك — النظام ما يقترح مبلغاً محدداً، القرار لك بالكامل."
        ),
    ),
    KBEntry(
        code="howto_payroll_month_end_reminder",
        title="هل النظام يذكّرني لو نسيت أجهّز راتب عامل؟",
        keywords=["تذكير رواتب", "نسيت راتب عامل", "تنبيه نهاية الشهر", "راتب متأخر"],
        body=(
            "شاشة 'التنبيهات' فيها تذكير تلقائي لكل عامل عنده راتب أساسي مسجَّل وما تأكَّد راتب شهره بعد — يظهر آخر 3 أيام من الشهر الحالي، وأي شهر سابق كامل فاتك تأكيده يبقى تذكيره ظاهراً 'متأخر' بشكل دائم (مهما مر عليه من وقت) لين تروح تأكّده. التذكير يذكر مبلغ الخصومات لو فيه مسودة محفوظة عليها خصومات."
        ),
    ),
    KBEntry(
        code="howto_travel_edit_confirmed_month_warning",
        title="عدّلت فترة سفر عامل وطلع لي تحذير عن راتب مؤكَّد — شنو أسوي؟",
        keywords=["تحذير راتب مؤكد", "تعديل سفر راتب مؤكد", "خصم راتب مؤكد لا يتغير"],
        body=(
            "الراتب المؤكَّد Snapshot ثابت عمداً — ما يتغيّر تلقائياً لو عدّلت فترة سفر تخص شهره بعد التأكيد (حتى لو صحّحت تاريخ خطأ). التحذير بس يعلمك بهذا — لو تبي تعدّل المبلغ المؤكَّد فعلاً، لازم تروح تعدّله يدوياً بشاشة الراتب نفسه (لو ما زال قابلاً للتعديل، وإلا يبقى كسجل تاريخي ثابت)."
        ),
    ),
    KBEntry(
        code="howto_payment_method_payroll",
        title="ما الفرق بين طريقة الدفع 'نقداً' و'تحويل بنكي' بالوصل؟",
        keywords=["طريقة الدفع الراتب", "تحويل بنكي وصل راتب", "دفع نقدي راتب", "مستلم الحوالة"],
        body=(
            "تُحدَّد مرة وحدة لكل عامل بشاشة 'إعداد الرواتب'. لو 'تحويل بنكي'، مسير الراتب يطبع 'من {صاحب الحلال} إلى {مستلم الحوالة}' صراحة — اسم المستلم حقل منفصل يُدخَل كل شهر بشكل مستقل بشاشة تجهيز الراتب (يختلف حسب الشهر، مثلاً لو حوّلت لأخو العامل مرة ولحسابه مباشرة مرة ثانية). لو 'نقداً'، يطبع 'طريقة الدفع: نقداً' بس بدون تفاصيل إضافية."
        ),
    ),
    KBEntry(
        code="howto_team_manage_salary_permission",
        title="مين يقدر يدير الرواتب بدون صلاحية كاملة على الفريق؟",
        keywords=["صلاحية ادارة الرواتب", "محاسب رواتب", "صلاحية منفصلة راتب"],
        body=(
            "صلاحية 'إدارة الرواتب' (team.manage_salary) منفصلة عمداً عن صلاحية 'إدارة الفريق' الكاملة (users.manage) — تُمنح افتراضياً لدور المحاسب. تغطي كل شاشات الرواتب (إعداد الأساسي، تجهيز/تأكيد الشهري، سجل السفر، بيانات صاحب الحلال) بدون ما تعطي القدرة على تغيير أدوار الأعضاء أو كلمات مرورهم أو تفعيل/تعطيل حساباتهم — تلك تبقى تحت 'إدارة الفريق' الكاملة بس."
        ),
    ),

    # ---------- تحليلات المالية الجديدة (بند إضافي 269 — صافي الربح، تشخيص الخسارة، الموسمية، القيمة السوقية) ----------

    KBEntry(
        code="howto_net_profit_percent",
        title="كيف أعرف نسبة ربحي الإجمالية؟",
        keywords=["نسبة ربحي", "صافي الربح", "نسبة الربح", "كم ارباحي", "هامش ربح المزرعة"],
        body=(
            "أعلى شاشة 'المالية' الرئيسية، بطاقتين: 'صافي الربح' (= إجمالي الداخل − إجمالي الخارج) و'نسبة الربح' (= صافي الربح ÷ إجمالي الخارج × 100). تتلوّن أحمر تلقائياً لو صرت بخسارة. الديون (دعم خارجي/سداد) مستثناة من الحسابين — التزام مو دخل أو مصروف تشغيلي حقيقي."
        ),
    ),
    KBEntry(
        code="howto_loss_diagnosis",
        title="أنا بخسارة، هل النظام يوضّح السبب؟",
        keywords=["ليش انا بخساره", "سبب الخسارة", "حل مشكلة الخسارة", "لماذا اخسر"],
        body=(
            "لو آخر 30 يوم صافيهم سالب، تطلع بطاقة '🔍 ليش أنا بخسارة؟' تلقائياً أعلى شاشة 'المالية' — تفصيل بنود مصروفك (شراء/مصروف) حسب الفئة، مرتبة من الأكبر، مع نسبتها من الإجمالي ونسبة تغيّرها عن الـ30 يوم اللي قبلها (يبيّن أي بند فعلاً زاد وبكم)، + عدد الرؤوس بهامش سالب فعلياً (من شاشة نقطة التعادل) مع رابط لمراجعتهم.\n"
            "النظام ما يقترح حل جاهز ('قلّل مصاريفك' مثلاً) — يعرض لك الحقائق الرقمية من بياناتك الفعلية بس، أنت تقرر الحل المناسب."
        ),
    ),
    KBEntry(
        code="howto_seasonal_price_chart",
        title="هل فيه شارت يوريني أفضل وقت لبيع الأغنام/الماعز؟",
        keywords=["افضل وقت للبيع", "موسمية اسعار البيع", "شارت اسعار البيع", "متى ابيع", "عيد الاضحى اسعار"],
        body=(
            "'المالية' ← 'موسمية أسعار البيع' — شارت مبني على التقويم **الهجري** (مو الميلادي، لأن عيد الأضحى يتحرك ~11 يوم كل سنة ميلادية) بعمودين لكل شهر هجري: أزرق = متوسط أسعار بيعك الحقيقية بهذا الشهر هالسنة، برتقالي = متوسط أسعار بيعك الحقيقية بنفس الشهر عبر كل السنين اللي عندك بيانات فيها. تظليل خفيف يبيّن رمضان وذو الحجة (فيه عيد الأضحى) — الموسمان الأكثر تأثيراً بسوق الأغنام/الماعز.\n"
            "**كل رقم من مبيعاتك الحقيقية بس — صفر بيانات سوق خارجية أو تخمين.** لو بياناتك من سنة هجرية وحدة بس، تطلع رسالة صريحة إن النمط لسا مو موثوق (يحتاج سنتين على الأقل)."
        ),
    ),
    KBEntry(
        code="howto_asset_maintenance",
        title="كيف أسجّل صيانة أصل (مولّد، سيارة...) وهل تكلفتها تدخل بالمالية؟",
        keywords=["صيانة اصل", "تكلفة صيانة", "اصلاح معدة", "صيانة مولد"],
        body=(
            "من 'المعدات' ← 'الأصول' ← اختر الأصل ← 'صيانة' — سجّل التاريخ والملاحظات وتكلفة الصيانة (اختياري). لو كتبت تكلفة، تُنشأ تلقائياً عملية 'مصروف' حقيقية بفئة 'صيانة معدات' تظهر بشاشة المالية وكل التقارير المبنية عليها — بدون أي إدخال إضافي منك."
        ),
    ),
    KBEntry(
        code="howto_utility_readings",
        title="كيف أسجّل فاتورة الكهرباء أو الماء؟",
        keywords=["فاتورة كهرباء", "فاتورة ماء", "استهلاك الطاقة", "قراءة عداد"],
        body=(
            "'المعدات' ← 'استهلاك الطاقة والماء' ← 'قراءة جديدة': نوع الاستهلاك (كهرباء/ماء)، الكمية والوحدة، وتكلفة الفاتورة (اختياري). لو كتبت تكلفة، تُنشأ تلقائياً عملية 'مصروف' حقيقية (فئة 'فاتورة كهرباء' أو 'فاتورة ماء') تظهر بالمالية. الهدف الأساسي من القراءات نفسها: كشف تغيّر مفاجئ (تسريب، مولّد يستهلك أكثر من المعتاد) بمقارنة القراءات مع الوقت."
        ),
    ),
    KBEntry(
        code="howto_team_performance_report",
        title="كيف أشوف أداء كل عامل بالفريق؟",
        keywords=["اداء العمال", "تقرير اداء الفريق", "تقييم اداء عامل", "افضل عامل"],
        body=(
            "'الفريق' ← 'تقرير الأداء' — لكل عامل عنده مهمة واحدة على الأقل محسومة (منجزة أو متعذّرة) بالفترة المختارة: نسبة الإنجاز، عدد المهام المتعذّرة، ونقطة أداء إجمالية من 100. الفترة الافتراضية أول الشهر الحالي لليوم، قابلة للتغيير من الفلتر. أعلى نقطة أداء بالشهر الماضي تظهر تلقائياً كشارة '🏆' بشاشة تجهيز راتب ذلك العامل (بند الرواتب) — نفس الرقم، بدون تكرار حساب."
        ),
    ),
    KBEntry(
        code="howto_task_quality_rate",
        title="كيف أقيّم جودة مهمة أنجزها عامل؟",
        keywords=["تقييم جودة مهمة", "تقييم اداء مهمة", "تصنيف جودة العمل"],
        body=(
            "'الفريق' ← 'المهام المنجزة اليوم': لكل مهمة منجزة اليوم، ثلاث أزرار تقييم سريعة (ضعيف/متوسط/ممتاز) مع حقل ملاحظة اختياري. يحتاج صلاحية 'مراجعة المهام اليومية' (صاحب الحلال/الدكتور/الممرض). التقييم يُسجَّل بسجل المهمة نفسه (مين قيّم ومتى)، ومستقل عن نقطة الأداء الإجمالية بتقرير الأداء (تلك مبنية على الإنجاز/التعذّر، مو على الجودة)."
        ),
    ),
    KBEntry(
        code="howto_break_even_screen",
        title="شنو يعني 'سعر التعادل' و'الهامش' بشاشة نقطة التعادل؟",
        keywords=["سعر التعادل", "شنو الهامش", "نقطة التعادل شرح", "التحليل المالي ونقطة التعادل"],
        body=(
            "'المالية' ← 'التحليل المالي ونقطة التعادل' — لكل رأس نشط:\n"
            "• 'سعر التعادل' = كل التكاليف المقدَّرة منذ دخوله (شراء + علاج + علف + نصيبه من المصاريف غير المباشرة) — أقل سعر بيع يغطي تكلفتك فعلياً، أي بيع تحته خسارة صافية.\n"
            "• 'الهامش' = القيمة التقديرية − سعر التعادل (راجع بند مصدر القيمة التقديرية لتفاصيل من وين تجي). هامش سالب (أحمر) = خطر خسارة لو بيع الآن.\n"
            "بطاقة 'رؤوس بهامش سالب' أعلى الشاشة تعد لك عدد الرؤوس المهدَّدة مباشرة."
        ),
    ),
    KBEntry(
        code="howto_culling_index",
        title="شنو هو 'مؤشر الاستبعاد المالي'؟",
        keywords=["مؤشر الاستبعاد المالي", "استبعاد اناث غير دافعة", "تكلفة الاحتفاظ برأس"],
        body=(
            "'المالية' ← 'مؤشر الاستبعاد المالي' — يحدد الإناث 'غير الدافعة' (بالغة بدون أي ولادة خلال آخر 400 يوم) ويحسب تكلفة استمرار الاحتفاظ بها شهرياً (علف + تكاليف صحية آخر 180 يوم)، مقابل قيمة إنتاجية = صفر (بحكم تعريف 'غير دافعة' نفسه).\n"
            "**النظام ما يبيع ولا يعزل أي رأس تلقائياً** — بس يحسب رقماً مالياً حقيقياً (تكلفة الفرصة البديلة) ويترك القرار لك. أنثى 'غير دافعة' ممكن سببها مؤقت (تأخر تقريع، مرض مؤقت) لا يستدعي استبعاداً — راجع دائماً سجلها الطبي والتكاثري قبل أي قرار بيع فعلي."
        ),
    ),
    KBEntry(
        code="howto_break_even_market_value",
        title="من وين تجي 'القيمة التقديرية' بشاشة نقطة التعادل؟",
        keywords=["القيمة التقديرية نقطة التعادل", "سعر السوق التقديري", "من وين القيمة التقديرية"],
        body=(
            "أولوية المصدر: (1) تقدير محسوب حي من متوسط أسعار بيع حقيقية لرؤوس مشابهة (نفس النوع/الجنس، عمر قريب) خلال آخر 90 يوم — يتحدّث تلقائياً كل مرة تفتح الشاشة، يظهر معه '📊 من N مبيعات مشابهة'. (2) لو ما فيه مبيعات كافية، يرجع للقيمة اليدوية المسجَّلة بشاشة 'بيانات تخطيط السوق' لو موجودة، ويظهر '✍️ تقدير يدوي'. (3) وإلا الهامش ما يُحسب أصلاً — النظام ما يخترع سعر سوق من عدم."
        ),
    ),

    # بند إضافي 306 — فجوة حقيقية اكتشفناها بالتدقيق: خطة "عقل المزرعة"
    # كاملة (بند 296-305) ما أضافت ولا بند معرفة وحد يشرح ميزاتها
    # الجديدة — نفس نمط الفجوة اللي بند 281 عالجها ("هل تم تحديث
    # المساعد بهذا البند؟"). لو مستخدم سأل المساعد نفسه عن هذي الميزات،
    # كان يوصله fallback عام بدون أي فايدة.
    KBEntry(
        code="howto_farm_notes",
        title="وش هو دفتر ملاحظات المزرعة، وكيف أستخدمه؟",
        keywords=["دفتر الملاحظات", "ملاحظات المزرعة", "farm notes", "اضافة ملاحظة"],
        body=(
            "'دفتر ملاحظات المزرعة' (رابط 📓 فوق شاشة المساعد الذكي) مكان تكتب فيه أي ملاحظة ميدانية حقيقية — سلوك حظيرة، سبب مشكلة تكرّرت، حل جرّبته وضبط معك — واختيارياً تربطها بحظيرة أو رأس معيّن.\n"
            "الفايدة: هذي الملاحظات تصير مصدر معرفة حقيقي أرجع له أنا (المساعد) مستقبلاً عند سؤال مشابه — مثلاً لو سألتني 'ليش الحظيرة الشرقية دايماً فيها مشكلة'، أقدر أسترجع ملاحظة سابقة كتبتها عنها. ما تُستخدم كقاعدة طبية ثابتة، مجرد سياق مرجعي."
        ),
    ),
    KBEntry(
        code="howto_smart_draft_entry",
        title="وش هو 'الإدخال الذكي'، وكيف أسجّل حدث أو أوزّع مهمة بالنص أو الصوت؟",
        keywords=["الادخال الذكي", "تسجيل بالصوت", "مسودة اعتماد", "سجلت ولادة", "وزع مهمة بالصوت", "smart entry"],
        body=(
            "شاشة 'الإدخال الذكي' (رابط 🎙️ فوق شاشة المساعد الذكي) تخليك تكتب أو تسجّل صوتياً حدثاً صار فعلاً بالمزرعة، بصيغة عامية طبيعية — مثلاً 'سجلت ولادة اليوم لشاة رقم 405'، 'سجلت وزن اليوم للرأس 900: 35 كيلو'، أو 'وزّع مهمة فحص حمل على الدكتور'.\n"
            "**قاعدة صارمة**: أنا أقترح مسودة بس — ما ينفَّذ أي شي فعلي بقاعدة البيانات إلا بعد ما تراجع البطاقة وتضغط 'اعتماد' بنفسك. المسودات المعلَّقة بدون قرار لمدة 48 ساعة تُحذف تلقائياً. الإجراءات المدعومة حالياً: تسجيل ولادة، تسجيل وزن، وتوزيع مهمة — أي شي يخص جرعة دواء أو حذف سجل يُرفض تلقائياً ولا يوصلك أصلاً كمسودة.\n"
            "**توزيع مهمة تحديداً (بند إضافي 316)**: أبداً ما أحدد أنا مين المكلَّف — بطاقة الاعتماد تعرض لك قائمة حقيقية بأسماء كل أعضاء الفريق تختار منها بنفسك. بعد اختيارك، أترجم نص المهمة تلقائياً للغة المسجَّلة لذاك الشخص بالضبط (لو مختلفة عن العربي) قبل ما توزَّع — النص الأصلي بالعربي يبقى محفوظاً بملاحظة المهمة."
        ),
    ),
    KBEntry(
        code="howto_animal_checkup_request",
        title="كيف أطلب من الدكتور يفحص رأس معيّن ويرفع تقرير؟",
        keywords=["طلب فحص شامل", "فحص رأس", "اطلب من الدكتور", "مهام فحص", "تقرير فحص"],
        body=(
            "افتح صفحة تفاصيل أي رأس، وتحت بطاقة 'طلب فحص شامل لهذا الرأس' اختر بنود الفحص اللي تبيها (حرارة، جلد، عين، خف، خراجات...)، أو اضغط '🤖 اقترح لي بنود الفحص' عشان أحلّل بيانات الرأس الحية (تنبيهاته، أمراضه المفتوحة، آخر وزن) وأقترح لك البنود المناسبة تلقائياً — تقدر تراجع وتعدّل قبل التوزيع.\n"
            "كل بند يصير مهمة مستقلة للدكتور، وإنجازه لها بملاحظة هو فعلياً تقريره — تقدر تشوف كل بنود نفس الطلب مجمَّعة ببعض من شاشة تفاصيل أي مهمة منها."
        ),
    ),
    KBEntry(
        code="howto_assistant_image_analysis",
        title="أقدر أرسل صورة للمساعد الذكي؟",
        keywords=["ارسال صورة", "ارسل صورة", "تحليل صورة", "رفع صوره للمساعد", "صورة حالة جلدية", "صورة للمساعد"],
        body=(
            "نعم — بشاشة المساعد الذكي، اضغط زر 📷 جنب صندوق الكتابة وارفع صورة (حالة جلدية، رقم أذن، صنف علف...) مع سؤالك النصي أو بدونه. أصف لك اللي أشوفه وأجاوب سؤالك، بس ممنوع أشخّص مرضاً نهائياً أو أقترح جرعة دواء من صورة — أي قرار علاجي نهائي لازم يمر على الطبيب البيطري."
        ),
    ),
]


def search(normalized_text: str, limit: int = 1) -> list[KBEntry]:
    """`normalized_text` لازم يكون مطبّع مسبقاً عبر `text_utils.normalize`.

    بند إصلاح — كان التسجيل بعدد الكلمات المفتاحية المطابقة فقط (1 لكل
    كلمة)، فسؤال محدد مثل "هل اقدر اسوي تحصين جماعي" كان يخسر أمام بند
    عام كلمته المفتاحية "تحصين" بس (نفس النقطة، بس أسبق بالترتيب داخل
    `ENTRIES` فيفوز بالتعادل). نستخدم طول الكلمة المطابقة كوزن بدل عدّها
    مرة وحدة — عبارة أدق وأطول ("تحصين جماعي") تفوز تلقائياً على كلمة
    عامة قصيرة ("تحصين") بدون حاجة نعيد ترتيب `ENTRIES` يدوياً."""
    scored = []
    for entry in ENTRIES:
        score = sum(len(kw) for kw in entry.normalized_keywords if kw in normalized_text)
        if score > 0:
            scored.append((score, entry))
    scored.sort(key=lambda pair: -pair[0])
    return [entry for _, entry in scored[:limit]]
