"""
سجل الصلاحيات المركزي.

الفكرة: أي "شي" يقدر مستخدم يسويه بالنظام له كود صلاحية ثابت هنا.
الأدوار (Roles) ما تُبنى بالكود، هي بيانات بقاعدة البيانات، وصاحب الحلال
يقدر ينشئ مسمى وظيفي جديد ويربطه بأي تركيبة من هالصلاحيات من واجهة الإعدادات
بدون الحاجة لأي تعديل برمجي.

هذا الملف بس يعرّف "القائمة الكاملة لكل صلاحية ممكنة" + التركيبة الافتراضية
لثلاثة أدوار جاهزة (مالك / دكتور / عامل) تُستخدم كنقطة بداية عند إعداد
النظام أول مرة (seed).
"""

# كل صلاحية: (code, description بالعربي)
PERMISSIONS = [
    # عام / نظام
    ("settings.manage", "إدارة إعدادات النظام وتفعيل/تعطيل الخدمات"),
    ("roles.manage", "إنشاء وتعديل المسميات الوظيفية والصلاحيات"),
    ("users.manage", "إضافة/تعديل/تعطيل حسابات المستخدمين"),
    ("team.manage_salary", "تعديل الراتب الأساسي لعضو الفريق (بدون بقية بيانات الحساب)"),
    ("audit.view", "الاطلاع على سجل التدقيق الكامل"),
    # ضبط المصنع (بند إضافي 282) — حذف كل بيانات المزرعة نهائياً
    # والرجوع لحالة تركيب جديدة. خطر جداً، وحصري لصاحب الحلال — عمداً
    # ما تُضاف لأي دور ثانٍ حتى لو مخصَّص، حتى لو `roles.manage` معطى له.
    ("system.factory_reset", "ضبط مصنع النظام (حذف كل البيانات نهائياً)"),

    # الحيوانات والحظائر
    ("animals.view", "عرض سجل الحيوانات"),
    ("animals.manage", "إضافة/تعديل/بيع/تسجيل نفوق حيوان"),
    ("sales.override_withdrawal", "بيع رأس داخل فترة سحب دواء بسبب موثَّق (بند إضافي 231)"),
    ("barns.manage", "إدارة الحظائر"),

    # الصحة والصيدلية
    ("health.view", "عرض السجل الصحي والزيارات البيطرية"),
    ("health.manage", "تسجيل تشخيص/علاج/تحصين"),
    ("pharmacy.manage", "إدارة مخزون الصيدلية"),
    ("medical_options.manage", "إضافة خيارات طبية جديدة (أعراض، أدوية، بروتوكولات)"),
    ("gates.approve", "اعتماد بوابات الخروج الحرجة (خروج من عزل، تقدّم مرحلة)"),

    # التكاثر
    ("repro.view", "عرض بيانات التكاثر (تلقيح، حمل، سونار، برامج شياع)"),
    ("repro.manage", "تسجيل تلقيح/تشخيص حمل/سونار وإدارة برامج الشياع التوأمي"),
    ("repro.override_close_relation", "تجاوز تحذير القرابة الوراثية عند التقريع مباشرة (بند إضافي 231)"),

    # المالية
    ("finance.health.view", "عرض المالية المرتبطة بالصحة والعلاج فقط"),
    ("finance.full.manage", "إدارة كامل المالية (مبيعات، مشتريات، ديون)"),

    # الفريق والمهام
    ("tasks.view_own", "عرض مهامي الشخصية فقط"),
    ("tasks.assign_any", "توزيع مهمة على أي عامل"),
    ("tasks.review_daily", "مراجعة المهام اليومية المقترحة تلقائياً (موافقة/تأجيل/حذف)"),
    ("tasks.delete_final", "حذف نهائي لمهمة (لا يملكها إلا صاحب الحلال)"),
    ("reports.submit", "رفع بلاغ"),
    ("reports.manage", "استلام/تحويل/إغلاق البلاغات"),
    ("reports.delete_final", "حذف نهائي لبلاغ ملغى (لا يملكها إلا صاحب الحلال)"),

    # العلف
    ("feed.view", "عرض بيانات العلف والمخزون"),
    ("feed.manage", "إدارة العلف والوصفات وخطط التغذية"),

    # مستودع المعدات (بند إضافي 108)
    ("equipment.view", "عرض مخزون المعدات"),
    ("equipment.manage", "إدارة مخزون المعدات (إضافة/شراء/صرف)"),

    # التقارير التحليلية (بند 22) — اسم مختلف عمداً عن reports.* الحالية
    # (تلك خاصة ببلاغات الفريق/التذاكر، مو التقارير التحليلية هنا).
    ("analytics.view", "عرض التقارير التحليلية (شامل، نفوق، ولادات، مبيعات) والتصدير"),

    # المساعد الذكي (بند 25)
    ("assistant.use", "استخدام المساعد الذكي التفاعلي والدردشة معه"),
    # دفتر ملاحظات المزرعة (بند إضافي 298 — المرحلة ٣ من خطة "عقل
    # المزرعة") — كتابة ملاحظة ميدانية جديدة تُغذّي ذاكرة المساعد
    # التراكمية. منفصلة عن `assistant.use` (اللي يسمح بس بالمحادثة/
    # القراءة) لأن الكتابة هنا تصير مصدر معرفة دائم يعتمد عليه المساعد،
    # قرار أثقل من مجرد سؤال.
    ("farm_notes.manage", "إضافة/تعديل ملاحظات دفتر المزرعة (مصدر ذاكرة المساعد الذكي)"),
    # الإدخال الذكي بالنص/الصوت (بند إضافي 299) — اقتراح مسودة إجراء
    # (تسجيل ولادة/وزن) عبر جملة حرة، واعتمادها البشري الصريح قبل أي
    # تنفيذ فعلي. صلاحية مستقلة عن `animals.manage` العادية عمداً —
    # المسار مختلف تماماً (نموذج ذكاء اصطناعي يقترح، إنسان يعتمد)،
    # وصاحب الحلال قد يبي يمنح هذا لعامل ميداني موثوق بدون كامل صلاحية
    # إدارة الحيوانات التقليدية (تعديل/بيع/نفوق مباشرة).
    ("assistant.draft_actions.confirm", "اعتماد أو رفض مسودات الإجراءات المقترحة من المساعد الذكي (نص/صوت)"),

    # رادار المناخ والإجهاد الحراري (بند إضافي 49)
    ("climate.view", "عرض توقعات الطقس ومؤشر الإجهاد الحراري"),
    ("climate.manage", "إعداد موقع المزرعة وحدود مؤشر الإجهاد الحراري"),
]

PERMISSION_CODES = {code for code, _ in PERMISSIONS}

# ترجمة إنجليزية لعرضها جنب الوصف العربي بشاشة "تعديل صلاحيات الدور"
# فقط (بند إضافي، طلبك الصريح: "عندك في اصلحيات خليها عربي انجليزي" —
# صلاحيات الدكتور/العامل/بقية أعضاء الفريق). لا تُستخدم بمكان ثانٍ —
# الوصف العربي بـPERMISSIONS أعلاه يبقى هو المخزَّن بعمود
# Permission.description بقاعدة البيانات كما كان، بدون أي تغيير.
PERMISSIONS_EN = {
    "settings.manage": "Manage system settings, enable/disable services",
    "roles.manage": "Create and edit job roles and their permissions",
    "users.manage": "Add/edit/deactivate user accounts",
    "team.manage_salary": "Edit a team member's base salary (only, not the rest of their account)",
    "audit.view": "View the full audit log",
    "system.factory_reset": "Factory reset the system (permanently deletes all data)",

    "animals.view": "View the animal records",
    "animals.manage": "Add/edit/sell/record death of an animal",
    "sales.override_withdrawal": "Sell an animal during its medicine withdrawal period, with a documented reason",
    "barns.manage": "Manage barns",

    "health.view": "View health records and vet visits",
    "health.manage": "Record a diagnosis/treatment/vaccination",
    "pharmacy.manage": "Manage the pharmacy stock",
    "medical_options.manage": "Add new medical options (symptoms, drugs, protocols)",
    "gates.approve": "Approve critical exit gates (leaving isolation, advancing a stage)",

    "repro.view": "View reproduction data (breeding, pregnancy, ultrasound, estrus programs)",
    "repro.manage": "Record breeding/pregnancy diagnosis/ultrasound and manage twinning-estrus programs",
    "repro.override_close_relation": "Override the close-relation genetic warning at direct breeding",

    "finance.health.view": "View only the finance linked to health and treatment",
    "finance.full.manage": "Manage all finance (sales, purchases, debts)",

    "tasks.view_own": "View only my own tasks",
    "tasks.assign_any": "Assign a task to any worker",
    "tasks.review_daily": "Review the auto-suggested daily tasks (approve/postpone/delete)",
    "tasks.delete_final": "Permanently delete a task (owner only)",
    "reports.submit": "Submit a report",
    "reports.manage": "Receive/forward/close reports",
    "reports.delete_final": "Permanently delete a cancelled report (owner only)",

    "feed.view": "View feed data and stock",
    "feed.manage": "Manage feed, rations, and feeding plans",

    "equipment.view": "View equipment stock",
    "equipment.manage": "Manage equipment stock (add/purchase/issue)",

    "analytics.view": "View analytics reports (overview, deaths, births, sales) and export",

    "assistant.use": "Use the interactive AI assistant and chat with it",
    "farm_notes.manage": "Add/edit farm notebook notes (the assistant's memory source)",
    "assistant.draft_actions.confirm": "Approve or reject action drafts suggested by the AI assistant (text/voice)",

    "climate.view": "View weather forecasts and the heat-stress index",
    "climate.manage": "Set the farm location and heat-stress index thresholds",
}

# التركيبة الافتراضية لثلاثة أدوار جاهزة عند أول تشغيل للنظام.
# هذي بس بيانات ابتدائية — صاحب الحلال يقدر يعدلها أو يضيف أدوار جديدة
# من واجهة الإعدادات بعد كذا بدون أي تعديل كود.
DEFAULT_ROLES = {
    "owner": {
        "display_name": "صاحب الحلال",
        "is_system": True,
        "permissions": list(PERMISSION_CODES),  # كل الصلاحيات
    },
    "doctor": {
        "display_name": "الدكتور",
        "is_system": True,
        "permissions": [
            "animals.view",
            "health.view", "health.manage",
            "pharmacy.manage", "medical_options.manage", "gates.approve",
            "repro.view", "repro.manage",
            "finance.health.view",
            "tasks.assign_any", "tasks.review_daily",
            "reports.manage",
            "feed.view",
            "equipment.view",
            "analytics.view",
            "assistant.use",
            "farm_notes.manage",
            "assistant.draft_actions.confirm",
            "climate.view",
            # بند إضافي (2026-08-31) — طلبك بعد صورة شاشة التنبيهات: زر
            # "فتح" لتنبيه "حظيرة بدون عامل مسؤول" (alerts_list.html)
            # كان موجوداً بالكود أصلاً، لكن مقيَّداً بصلاحية barns.manage
            # اللي الدكتور ما يملكها افتراضياً — يطلعله التنبيه بلا زر
            # ولا أي توضيح ليش. الدكتور غالباً أنسب شخص يحل هذا النوع
            # من التنبيهات (تعيين عامل مسؤول لحظيرة)، فأضفنا الصلاحية
            # لدوره الافتراضي.
            "barns.manage",
            # بند إضافي (2026-08-31، طلبك المباشر بعد نقاش صلاحيات
            # الدكتور) — قراران استثنائيان طبيان/تكاثريان بحتان، كانا
            # مقصورين على صاحب الحلال بس، رغم إن الدكتور هو أنسب شخص
            # يقيّم صحتهما فعلياً:
            "sales.override_withdrawal",  # بيع رأس أثناء سحب دواء بسبب موثَّق
            "repro.override_close_relation",  # تجاوز تحذير القرابة الوراثية بالتقريع المباشر
            # بند إضافي (2026-08-31) — اكتشفنا إن sales.override_withdrawal
            # فوق كانت بلا فايدة عملياً: شاشة "بيع الحيوان" كاملة (اللي
            # فيها خيار التجاوز) محجوبة أصلاً خلف animals.manage، والدكتور
            # ما يملكها. طلبك الصريح: أعطه animals.manage كاملة (تثق فيه) —
            # صار يقدر يضيف/يعدّل/يبيع/يسجّل نفوق حيوان مباشرة، مو بس يشوف.
            "animals.manage",
        ],
    },
    "worker": {
        "display_name": "العامل",
        "is_system": True,
        "permissions": [
            "tasks.view_own",
            "reports.submit",
            "assistant.use",
            "assistant.draft_actions.confirm",
            # عرض شاشة "معداتي" المبسّطة (بند إضافي 199) — أخذ/استرجاع
            # معدات بضغطة وحدة، بدون صلاحية إدارة مخزون كاملة.
            "equipment.view",
        ],
    },
    # بند إضافي — طلب صريح: مسمّى وظيفي ثاني منفصل عن "العامل" لمن يشتغل
    # بالجانب الزراعي/الأعلاف تحديداً (مو رعاية الحيوان اليومية). بدون
    # أي صلاحيات مبدئياً بطلبك الصريح — تحدّدها بنفسك لاحقاً من "الأدوار
    # والصلاحيات" ← تعديل هذا الدور، نفس أي مسمّى وظيفي مخصَّص تضيفه
    # يدوياً. `is_system: False` (زي أي دور تضيفه بنفسك من شاشة "مسمّى
    # وظيفي جديد") — يميّزه عن الأدوار الجاهزة الأساسية فقط.
    "farm_worker": {
        "display_name": "عامل زراعي",
        "is_system": False,
        "permissions": [],
    },
    "construction_worker": {
        "display_name": "عامل بناء",
        "is_system": False,
        "permissions": [],
    },
    # بند إضافي — طلب صريح لتمييزه عن "عامل زراعي" (اللي ممكن يكون
    # زراعة/أعلاف بس، بدون رعاية حيوان مباشرة): مسمّى وظيفي مخصَّص
    # لمن يشتغل فعلياً برعاية القطيع اليومية (تنظيف، تغذية، فحص).
    "livestock_worker": {
        "display_name": "عامل تربية مواشي",
        "is_system": False,
        "permissions": [],
    },
    "farm_manager": {
        "display_name": "مدير مزرعة",
        "is_system": False,
        "permissions": [],
    },
    "nurse": {
        "display_name": "الممرض",
        "is_system": True,
        "permissions": [
            # ينفّذ العلاج/الجرعة/التحصين المعتمد من الدكتور، ويسجّل ما
            # نُفّذ فعلياً — بدون صلاحية تحديد تشخيص أو دور دكتور كامل.
            "animals.view",
            "health.view", "health.manage",
            "pharmacy.manage",
            "tasks.view_own",
            "reports.submit",
            "assistant.use",
            # مراجعة مهام الفريق اليومية وتقييم جودتها (بند إضافي 229) —
            # بطلبك الصريح: صاحب الحلال/الدكتور/الممرض يقدرون يراجعون
            # مهام اليوم المنجزة.
            "tasks.review_daily",
            "farm_notes.manage",
            "assistant.draft_actions.confirm",
        ],
    },
    "accountant": {
        "display_name": "المحاسب",
        "is_system": True,
        "permissions": [
            "animals.view",
            "finance.full.manage",
            "analytics.view",
            "assistant.use",
            # بند إضافي 241 — بطلبك الصريح: المحاسب يقدر يضيف/يعدّل
            # الراتب الأساسي لعضو الفريق، بدون صلاحية إدارة الحسابات
            # الكاملة (users.manage).
            "team.manage_salary",
        ],
    },
    "viewer": {
        "display_name": "مشاهد",
        "is_system": True,
        "permissions": [
            # قراءة فقط بشكل افتراضي — صاحب الحلال يقدر يوسّع صلاحياته
            # من شاشة "تعديل الصلاحيات" بالإعدادات حسب الحاجة.
            "animals.view",
            "health.view",
            "analytics.view",
            "assistant.use",
        ],
    },
}
