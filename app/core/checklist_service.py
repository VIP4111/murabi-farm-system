"""محرك دليل المربي المبتدئ والتوجيه اليومي/الأسبوعي (بند إضافي 168).

الفكرة: بدل ما ينتظر المستخدم يسأل المساعد الذكي، تُعرض له تلقائياً
بالصفحة الرئيسية قائمة تحقق قصيرة تتغيّر حسب مرحلة القطيع الفعلية
(`active_stages`) ودوره الوظيفي وهل هو "مبتدئ" أو لا — مو قائمة واحدة
ثابتة للجميع، ومو قائمة انتظار لسؤال يُطرح."""
from datetime import date, timedelta
from flask_babel import lazy_gettext as _l
from app.extensions import db
from app.models import ChecklistItem, ChecklistCompletion, Animal, Pregnancy, Barn


def active_stages() -> set[str]:
    """يفحص حالة القطيع الفعلية حالياً ويرجّع مجموعة المراحل النشطة —
    "عام" و"تجهيز" دائماً نشطتان (كل مزرعة بحاجتهما بغض النظر عن حالة
    القطيع)، البقية تُفعَّل بس لو فيها بيانات فعلية تطابقها الآن."""
    stages = {"general", "prep"}

    if Animal.query.filter_by(status="active", purpose="تسمين").first():
        stages.add("fattening")

    pregnant = (
        Pregnancy.query.filter_by(confirmed=True)
        .join(Animal, Pregnancy.female_id == Animal.id)
        .filter(Animal.status == "active")
        .first()
    )
    if pregnant:
        stages.add("pregnancy")

    from app.core.animal_filters_service import get_filtered
    if get_filtered("ready_to_mate"):
        stages.add("estrus")

    newborn_in_isolation = (
        Animal.query.join(Barn, Animal.barn_id == Barn.id)
        .filter(Barn.barn_type == "عزل", Animal.status == "active")
        .first()
    )
    if newborn_in_isolation:
        stages.add("birth")

    return stages


def _period_key(frequency: str, today: date) -> str:
    if frequency == "daily":
        return today.isoformat()
    if frequency == "weekly":
        start = today - timedelta(days=today.weekday())
        return start.isoformat()
    return "once"


NEGLECT_LOOKBACK_PERIODS = 4
NEGLECT_THRESHOLD = 2


def _prior_period_keys(frequency: str, today: date, lookback: int) -> list[str]:
    """آخر `lookback` فترة *قبل* الفترة الحالية (ما يشملها) — تُستخدم
    لحساب سجل التجاهل، مو لعرض بند الفترة الحالية نفسه."""
    if frequency == "daily":
        return [(today - timedelta(days=i)).isoformat() for i in range(1, lookback + 1)]
    if frequency == "weekly":
        current_start = today - timedelta(days=today.weekday())
        return [(current_start - timedelta(weeks=i)).isoformat() for i in range(1, lookback + 1)]
    return []


def _miss_streak(user, item: "ChecklistItem", today: date) -> int:
    """عدد الفترات المتتالية الأخيرة (بدءاً من أقرب فترة سابقة) اللي ما
    أنجز فيها المستخدم هذا البند — يتوقف العدّ أول فترة مُنجَزة. بند
    "once" دائماً 0 (ما ينطبق عليه مفهوم التكرار)."""
    keys = _prior_period_keys(item.frequency, today, NEGLECT_LOOKBACK_PERIODS)
    if not keys:
        return 0
    done_keys = {
        c.period_key for c in ChecklistCompletion.query.filter(
            ChecklistCompletion.user_id == user.id,
            ChecklistCompletion.checklist_item_id == item.id,
            ChecklistCompletion.period_key.in_(keys),
        ).all()
    }
    streak = 0
    for key in keys:
        if key in done_keys:
            break
        streak += 1
    return streak


def daily_checklist_for(user, today: date | None = None) -> list[dict]:
    """يرجّع قائمة عناصر الدليل المناسبة لهذا المستخدم الآن: تطابق
    مرحلة نشطة + (دوره الوظيفي أو "all") + (لو "beginner" فقط لمن فعّل
    وسم المبتدئ)، مع حالة الإنجاز الحالية لكل عنصر.

    **الأولوية التكيّفية (بند إضافي 172)**: أي بند يومي/أسبوعي تجاهله
    المستخدم `NEGLECT_THRESHOLD` فترة متتالية فأكثر يُعلَّم `neglected`
    ويُرفَع لأعلى القائمة (بدل ترتيب المرحلة/sort_order الثابت) — تكثيف
    فعلي للأولوية داخل الواجهة نفسها، مو مجرد عدّاد صامت."""
    today = today or date.today()
    stages = active_stages()
    role_name = user.role.name if user.role else None

    candidate_roles = {"all", role_name}
    if user.is_beginner:
        candidate_roles.add("beginner")

    items = (
        ChecklistItem.query.filter(
            ChecklistItem.is_active.is_(True),
            ChecklistItem.stage.in_(stages),
            ChecklistItem.target_role.in_(candidate_roles),
        )
        .order_by(ChecklistItem.stage, ChecklistItem.sort_order)
        .all()
    )

    result = []
    for item in items:
        period_key = _period_key(item.frequency, today)
        done = ChecklistCompletion.query.filter_by(
            user_id=user.id, checklist_item_id=item.id, period_key=period_key,
        ).first() is not None
        miss_streak = 0 if done else _miss_streak(user, item, today)
        result.append({
            "item": item, "period_key": period_key, "done": done,
            "miss_streak": miss_streak, "neglected": miss_streak >= NEGLECT_THRESHOLD,
        })

    result.sort(key=lambda r: (r["done"], -r["miss_streak"]))
    return result


def toggle_completion(user, item_id: int, today: date | None = None) -> bool:
    """يقلب حالة الإنجاز (لو موجودة يحذفها، لو مو موجودة يضيفها) —
    يرجّع الحالة الجديدة (True = مُنجَز الآن)."""
    item = ChecklistItem.query.get_or_404(item_id)
    today = today or date.today()
    period_key = _period_key(item.frequency, today)
    existing = ChecklistCompletion.query.filter_by(
        user_id=user.id, checklist_item_id=item.id, period_key=period_key,
    ).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return False
    db.session.add(ChecklistCompletion(
        user_id=user.id, checklist_item_id=item.id, period_key=period_key,
    ))
    db.session.commit()
    return True


# الجولة المكثّفة أول دخول (بند إضافي 2026-08-31، طلبك المباشر: "ابيه
# شرح مكثف... اشروحات على حسب الصلحيات المعطا فقط") — كل قسم مربوط
# بصلاحية فعلية (`user.has_permission()`) بدل اسم الدور الثابت، عشان
# يشتغل صح حتى لو صاحب الحلال خصّص صلاحيات دور معيّن يدوياً (دور مخصَّص
# ما يطابق "owner/doctor/worker" بالاسم، لكن يملك تركيبة صلاحيات
# حقيقية). كل نص مغلَّف بـ_l() فيُترجم فعلياً حسب لغة الحساب — مصدر
# واحد بالكود (مو بيانات قاعدة بيانات تحتاج عمود ترجمة منفصل لكل لغة).
# بند إضافي (2026-08-31، طلبك المباشر: "تعزيز الجولة التعريفية") —
# فئات لتجميع الأقسام بعناوين فرعية بالشاشة، بدل قائمة مسطّحة من 20+
# قسم متتالي بلا تصنيف (صعبة المسح البصري خصوصاً لصاحب الحلال اللي
# يملك كل الصلاحيات ويشوف الجولة كاملة). ترتيب الفئات نفسه ترتيب أهم
# استخدام يومي أولاً (عام → حيوانات → صحة → تكاثر...).
_CAT_GENERAL = _l("عام")
_CAT_ANIMALS = _l("الحيوانات والحظائر")
_CAT_HEALTH = _l("الصحة والصيدلية")
_CAT_REPRO = _l("التكاثر")
_CAT_FINANCE = _l("المالية")
_CAT_TASKS = _l("المهام والبلاغات")
_CAT_FEED = _l("العلف")
_CAT_EQUIPMENT = _l("المعدات")
_CAT_ANALYTICS = _l("التقارير التحليلية")
_CAT_ASSISTANT = _l("المساعد الذكي")
_CAT_CLIMATE = _l("المناخ")
_CAT_ADMIN = _l("الفريق والصلاحيات")

_TOUR_SECTIONS = [
    {
        "permission": None,  # قسم عام — يظهر لأي مستخدم مسجّل دخول بغض النظر عن صلاحياته
        "category": _CAT_GENERAL,
        "icon": "🏠",
        "title": _l("الصفحة الرئيسية و«صفحة اليوم»"),
        "points": [
            _l("الصفحة الرئيسية تعرض «إجراءات سريعة» لأكثر الشاشات استخداماً حسب صلاحياتك، وتنبيهات فورية لو فيه شي يحتاج انتباهك."),
            _l("«صفحة اليوم» (من الرئيسية) تجمع مهامك المفتوحة وتنبيهاتك وبلاغاتك بشاشة وحدة بدل ما تتنقّل بين عدة شاشات كل صباح."),
        ],
        "link_endpoint": "core.today",
    },
    {
        "permission": "animals.view",
        "category": _CAT_ANIMALS,
        "icon": "🐑",
        "title": _l("سجل الحيوانات"),
        "points": [
            _l("كل رأس بالقطيع له سجل مستقل: رقمه، فصيلته، سلالته، عمره، حظيرته، وحالته الحالية (نشط/مباع/نافق/معزول)."),
            _l("كل شاشة ثانية بالنظام (الصحة، التكاثر، العلف، التقارير) مبنية على وجود سجل حيوان أولاً."),
        ],
        "link_endpoint": "core.animals_list",
    },
    {
        "permission": "animals.manage",
        "category": _CAT_ANIMALS,
        "icon": "➕",
        "title": _l("إضافة/تعديل/بيع حيوان"),
        "points": [
            _l("تقدر تسجّل حيوان جديد (واحد أو دفعة شراء كاملة)، تعدّل بياناته، تسجّل بيعه أو نفوقه."),
            _l("بيع حيوان أثناء فترة سحب دواء يحتاج سبباً موثَّقاً — النظام يمنع البيع العادي تلقائياً بهذي الحالة حماية للمستهلك."),
        ],
    },
    {
        "permission": "barns.manage",
        "category": _CAT_ANIMALS,
        "icon": "🏚️",
        "title": _l("إدارة الحظائر"),
        "points": [
            _l("أنشئ حظائرك وحدد نوعها (عادية/عزل/نفاس...) وسعتها والعامل المسؤول عنها."),
            _l("حظيرة العزل ضرورية — العزل التلقائي بعد الولادة أو وصول حيوان جديد يحتاج حظيرة عزل موجودة فعلاً."),
        ],
        "link_endpoint": "core.barns_list",
    },
    {
        "permission": "health.view",
        "category": _CAT_HEALTH,
        "icon": "🩺",
        "title": _l("السجل الصحي والزيارات البيطرية"),
        "points": [
            _l("تاريخ كل حالة مرضية، تشخيص، علاج، وتحصين لكل رأس — بما فيها المساعد التشخيصي اللي يقترح احتمالات مرضية من الأعراض المُدخَلة."),
        ],
        "link_endpoint": "health.diseases_list",
    },
    {
        "permission": "health.manage",
        "category": _CAT_HEALTH,
        "icon": "💉",
        "title": _l("تسجيل تشخيص/علاج/تحصين"),
        "points": [
            _l("سجّل حالة مرضية جديدة، طبّق بروتوكول علاج جاهز، أو سجّل تحصيناً — كل إجراء يخصم تلقائياً من مخزون الصيدلية ويُحسب ماليته."),
            _l("تنبيه: النظام يساعدك تنظّم وتتذكّر، لكنه ما يشخّص ولا يعالج — القرار الطبي النهائي يبقى للطبيب البيطري دائماً."),
        ],
    },
    {
        "permission": "pharmacy.manage",
        "category": _CAT_HEALTH,
        "icon": "💊",
        "title": _l("إدارة مخزون الصيدلية"),
        "points": [
            _l("سجّل الأدوية بكمياتها (عدد العلب × كمية العلبة يحسب الإجمالي تلقائياً)، وتابع تنبيهات نفاد المخزون."),
        ],
        "link_endpoint": "health.pharmacy_list",
    },
    {
        "permission": "repro.view",
        "category": _CAT_REPRO,
        "icon": "👶",
        "title": _l("التكاثر: تلقيح، حمل، ولادة"),
        "points": [
            _l("تابع دورة كل أنثى — من التقريع إلى تشخيص الحمل (فحص يدوي أو سونار) إلى الولادة — وتاريخ الولادة المتوقع يُحسب تلقائياً."),
        ],
        "link_endpoint": "repro.matings_list",
    },
    {
        "permission": "repro.manage",
        "category": _CAT_REPRO,
        "icon": "🐏",
        "title": _l("تسجيل تقريع وبرامج شياع"),
        "points": [
            _l("سجّل محاولة تقريع بين أنثى وفحل — النظام يحذّرك تلقائياً لو فيه قرابة وراثية قريبة بينهما قبل ما تحفظ."),
        ],
    },
    {
        "permission": "finance.health.view",
        "category": _CAT_FINANCE,
        "icon": "💰",
        "title": _l("المالية المرتبطة بالصحة"),
        "points": [
            _l("تكلفة كل علاج/تحصين/زيارة بيطرية تُسجَّل مالياً تلقائياً — تقدر تراجعها من هنا بدون صلاحية المالية الكاملة."),
        ],
    },
    {
        "permission": "finance.full.manage",
        "category": _CAT_FINANCE,
        "icon": "📊",
        "title": _l("المالية الكاملة"),
        "points": [
            _l("كل حركة مالية بالمزرعة: مبيعات، مشتريات، ديون، فواتير — من هنا تدير كامل الجانب المالي."),
        ],
        "link_endpoint": "finance.finance_list",
    },
    {
        "permission": "tasks.assign_any",
        "category": _CAT_TASKS,
        "icon": "📋",
        "title": _l("توزيع ومراجعة المهام"),
        "points": [
            _l("النظام يقترح مهاماً يومية تلقائياً حسب حالة القطيع (فحص عزل، متابعة حمل...)، وتقدر توزّع مهاماً يدوية على أي عامل."),
            _l("قسم «مهام مقترحة بانتظار الاعتماد» يحتاج موافقتك (أو تأجيل/حذف) قبل ما تنزل فعلياً للعامل."),
        ],
        "link_endpoint": "team.tasks_list",
    },
    {
        "permission": "tasks.view_own",
        "category": _CAT_TASKS,
        "icon": "✅",
        "title": _l("مهامي"),
        "points": [
            _l("قائمة مهامك الشخصية المفتوحة — ابدأ المهمة، أنجزها (مع صورة/ملاحظة إثبات لو مطلوبة)، أو سجّل تعذّر تنفيذها بسبب واضح."),
        ],
        "link_endpoint": "team.tasks_list",
    },
    {
        "permission": "reports.submit",
        "category": _CAT_TASKS,
        "icon": "📢",
        "title": _l("رفع بلاغ"),
        "points": [
            _l("لاحظت شي غير طبيعي بالحظيرة؟ ارفع بلاغاً فورياً (نص أو ملاحظة صوتية) يوصل للمسؤول مباشرة."),
        ],
    },
    {
        "permission": "reports.manage",
        "category": _CAT_TASKS,
        "icon": "📥",
        "title": _l("استلام وإدارة البلاغات"),
        "points": [
            _l("استلم بلاغات الفريق، حوّلها لعامل ثاني لو يلزم، أو أغلقها بعد المعالجة."),
        ],
        "link_endpoint": "team.reports_list",
    },
    {
        "permission": "feed.view",
        "category": _CAT_FEED,
        "icon": "🌾",
        "title": _l("العلف والمخزون"),
        "points": [
            _l("تابع أصناف العلف المتوفرة، خطط التغذية لكل حظيرة، ومعدل تحويل العلف (FCR) لتسمين القطعان."),
        ],
        "link_endpoint": "feed.items_list",
    },
    {
        "permission": "feed.manage",
        "category": _CAT_FEED,
        "icon": "🧮",
        "title": _l("إدارة العلف والوصفات"),
        "points": [
            _l("أضف أصناف علف جديدة، سجّل مشتريات، وابنِ وصفات علف موزونة (موازن العليقة يقترح أرخص تركيبة تحقق احتياج البروتين/الطاقة)."),
        ],
    },
    {
        "permission": "equipment.view",
        "category": _CAT_EQUIPMENT,
        "icon": "🧰",
        "title": _l("مخزون المعدات"),
        "points": [
            _l("تابع معدات المزرعة وأدواتها — المتوفر منها ومين مسحوب عنده حالياً."),
        ],
        "link_endpoint": "equipment.items_list",
    },
    {
        "permission": "analytics.view",
        "category": _CAT_ANALYTICS,
        "icon": "📈",
        "title": _l("التقارير التحليلية"),
        "points": [
            _l("تقارير شاملة: نفوق، ولادات، مبيعات، أداء القطيع — قابلة للتصدير لمشاركتها أو أرشفتها."),
        ],
        "link_endpoint": "reports.overview",
    },
    {
        "permission": "assistant.use",
        "category": _CAT_ASSISTANT,
        "icon": "🤖",
        "title": _l("المساعد الذكي"),
        "points": [
            _l("اسأله أي سؤال تشغيلي عام (تحصينات، عزل، فترات سحب...) أو اطلب منه معلومة عن حيوان معيّن — يجاوب من بيانات مزرعتك الفعلية."),
            _l("تنبيه: مساعد قرار مساعد لك، مو طبيباً بيطرياً — القرار الطبي النهائي يبقى للطبيب دائماً."),
        ],
        "link_endpoint": "assistant.chat",
    },
    {
        "permission": "climate.view",
        "category": _CAT_CLIMATE,
        "icon": "🌡️",
        "title": _l("رادار المناخ والإجهاد الحراري"),
        "points": [
            _l("توقعات الطقس ومؤشر الإجهاد الحراري لموقع مزرعتك — يساعدك تتوقع أيام الخطر وتجهّز التبريد/التهوية مسبقاً."),
        ],
        "link_endpoint": "climate.dashboard",
    },
    {
        "permission": "roles.manage",
        "category": _CAT_ADMIN,
        "icon": "🔑",
        "title": _l("إدارة المسمّيات الوظيفية والصلاحيات"),
        "points": [
            _l("أنشئ مسمّيات وظيفية جديدة أو عدّل صلاحيات أي دور موجود من شاشة الإعدادات — بدون أي حاجة لتعديل برمجي."),
        ],
        "link_endpoint": "core.settings_home",
    },
    {
        "permission": "users.manage",
        "category": _CAT_ADMIN,
        "icon": "👥",
        "title": _l("إدارة حسابات الفريق"),
        "points": [
            _l("أضف أعضاء فريق جدد، عطّل حساباً، أو عدّل بياناتهم من شاشة «الفريق»."),
        ],
        "link_endpoint": "team.members_list",
    },
]


def permission_tour_sections(user) -> list[dict]:
    """أقسام الجولة المكثّفة أول دخول — كل قسم يظهر فقط لو المستخدم
    يملك الصلاحية المرتبطة فعلياً (`has_permission`)، مو حسب اسم الدور.
    القسم العام (permission=None) يظهر للجميع دائماً."""
    return [
        s for s in _TOUR_SECTIONS
        if s["permission"] is None or user.has_permission(s["permission"])
    ]


def permission_tour_grouped(user) -> list[dict]:
    """نفس permission_tour_sections بس مجمَّعة بفئات ({"category",
    "sections"}) — تجميع يدوي بترتيب الإدراج الأصلي (مو Jinja groupby،
    اللي يفرز الفئات أبجدياً حسب النص المترجَم الحالي، فيغيّر ترتيب
    الفئات حسب لغة الحساب بدل ترتيب الأهمية/الاستخدام المقصود)."""
    sections = permission_tour_sections(user)
    groups: list[dict] = []
    for s in sections:
        if groups and groups[-1]["category"] == s["category"]:
            groups[-1]["sections"].append(s)
        else:
            groups.append({"category": s["category"], "sections": [s]})
    return groups


def onboarding_steps_for(user) -> list[ChecklistItem]:
    """خطوات مسار الترحيب أول دخول — عناصر مرحلة "عام" وتكرار "once"
    المستهدَفة لدور المستخدم (أو "all")، بغض النظر عن `active_stages`
    (الترحيب يظهر مرة واحدة دائماً، مو مشروطاً بحالة القطيع)."""
    role_name = user.role.name if user.role else None
    candidate_roles = {"all", role_name}
    if user.is_beginner:
        candidate_roles.add("beginner")
    return (
        ChecklistItem.query.filter(
            ChecklistItem.is_active.is_(True),
            ChecklistItem.stage == "general",
            ChecklistItem.frequency == "once",
            ChecklistItem.target_role.in_(candidate_roles),
        )
        .order_by(ChecklistItem.sort_order)
        .all()
    )
