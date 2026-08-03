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
    ("audit.view", "الاطلاع على سجل التدقيق الكامل"),

    # الحيوانات والحظائر
    ("animals.view", "عرض سجل الحيوانات"),
    ("animals.manage", "إضافة/تعديل/بيع/تسجيل نفوق حيوان"),
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

    # رادار المناخ والإجهاد الحراري (بند إضافي 49)
    ("climate.view", "عرض توقعات الطقس ومؤشر الإجهاد الحراري"),
    ("climate.manage", "إعداد موقع المزرعة وحدود مؤشر الإجهاد الحراري"),
]

PERMISSION_CODES = {code for code, _ in PERMISSIONS}

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
            "climate.view",
        ],
    },
    "worker": {
        "display_name": "العامل",
        "is_system": True,
        "permissions": [
            "tasks.view_own",
            "reports.submit",
            "assistant.use",
        ],
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
