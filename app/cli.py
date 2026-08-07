import click
from app.extensions import db
from app.models import Role, Permission, User, ServiceToggle, DiseaseType, Symptom, DiseaseSymptomLink, DailyTaskTemplate, EmergencySymptom
from app.permissions_registry import PERMISSIONS, DEFAULT_ROLES
from app.disease_library_data import DISEASE_LIBRARY_V2, DISEASE_ALIAS_MAP

# مهام يومية ثابتة افتراضية (بند إضافي 107) — كانت مكتوبة بالكود مباشرة
# بـdaily_task_service._rule_definitions قبل هذا البند؛ صارت بيانات
# بقاعدة البيانات، قابلة للتعديل من شاشة "مهام العامل التلقائية" بدون
# أي تعديل كود.
DEFAULT_DAILY_TASK_TEMPLATES = [
    ("🧹 تنظيف المعالف والحظائر", "راجع جفاف الأرضية والتهوية والزحام، ونظّف المعالف والمشارب."),
    ("💧 فحص الماء والأملاح", "تأكد من نظافة المشارب وتوفر ماء نظيف وأملاح مناسبة طوال اليوم."),
    ("🔍 فحص يومي للقطيع", "افحص الشهية والاجترار والحركة والتنفس والبراز والعرج والجروح بكل الحظائر."),
]


DEFAULT_SERVICES = [
    ("crm", "إدارة العملاء (CRM)", "يحتاج: بيانات العملاء الأساسية (اسم، جوال) قبل تسجيل أول عملية بيع."),
    ("multi_branch", "تعدد الفروع", "يحتاج: اسم كل فرع وموقعه. التقارير تصير موحّدة لك تلقائياً."),
    ("multi_language", "لغات إضافية للعمال", "يحتاج: تحديد لغة كل عامل من ملفه الشخصي (عربي/إنجليزي/أمهرية/هندية)."),
    ("suppliers", "إدارة الموردين والمشتريات", "يحتاج: تسجيل بيانات كل مورد قبل ربط فواتير الشراء به."),
    ("genetics", "الأنساب والقيمة الوراثية", "يحتاج: تعبئة الأب والأم لكل حيوان قدر الإمكان لدقة أفضل."),
    # بند إضافي 123 — تسجيل دخول سريع للتجربة/التطوير بس. تحذير أمني
    # صريح بالنشرة نفسها لأن الفحص الخادمي بـ`auth.quick_login` يرفض
    # الطلب لو الخدمة موقوفة، بس القرار بالتفعيل يبقى للمالك.
    ("dev_quick_login", "تسجيل دخول سريع (وضع تجربة)",
     "⚠️ تحذير أمني: يعرض قائمة كل الحسابات على شاشة الدخول ويدخل بضغطة وحدة بدون كلمة مرور. "
     "للتجربة أو التطوير فقط — لا تفعّلها على موقع حقيقي يستخدمه فريقك."),
]

# قائمة أمراض شائعة بالأغنام والماعز (بند إضافي، 2026-07-23) — أسماء
# معروفة فقط لتسريع الإدخال، بدون أي علاج أو جرعة. نقطة بداية معقولة،
# قابلة للتوسيع بالكامل من شاشة "الأمراض الشائعة" لاحقاً بدون كود.
DEFAULT_DISEASE_TYPES = [
    "التهاب الضرع", "الجرب", "الديدان المعوية", "الإسهال", "الالتهاب الرئوي",
    "التسمم الدموي المعوي", "الحمى القلاعية", "تعفن الظلف", "التهاب الملتحمة",
    "الجدري", "الكزاز", "نقص الكالسيوم",
]

# شجرة القرار التشخيصية (بند إضافي، 2026-07-24) — روابط مرض↔عرض معروفة
# ومنشورة بمراجع صحة الحيوان الأساسية (نفس مستوى "قائمة أمراض شائعة"
# الموجودة أصلاً)، الوزن (1-3) يعكس قوة الدلالة: 3=دليل قوي مميّز،
# 2=شائع، 1=محتمل/مصاحب. **مرجع مطابقة أنماط للمساعدة بترتيب الاحتمالات
# بس** — الحالة تبقى "مفتوحة" لين ما يراجعها الدكتور فعلياً ويوثّق
# تعافي (نفس قاعدة 12.3 الموجودة أصلاً، `Disease.status`).
DEFAULT_SYMPTOMS_PRIMARY = [
    "حرارة", "إسهال", "عرج", "سعال وصعوبة تنفس", "تورم أو احمرار بالضرع",
    "حكة وتساقط شعر", "تقرحات بالفم أو القوائم", "إفرازات من العين",
    "تيبّس بالعضلات وتشنجات", "ضعف عام وعدم قدرة على الوقوف",
    "بثور أو حبوب على الجلد", "فقدان وزن رغم الأكل",
    # عرض طوارئ (بند إضافي 51) — اسمه محجوز حرفياً بمنطق
    # health_service.EMERGENCY_SYMPTOMS، أي تعديل بالنص يكسر الربط.
    "عمى مفاجئ / عتامة العين",
]

DISEASE_SYMPTOMS = {
    "التهاب الضرع": [("تورم أو احمرار بالضرع", 3), ("حرارة", 2), ("انخفاض إنتاج الحليب المفاجئ", 3), ("تكتل أو تغيّر قوام الحليب", 2)],
    "الجرب": [("حكة وتساقط شعر", 3), ("تقشّر بالجلد", 2), ("فقدان وزن رغم الأكل", 1)],
    "الديدان المعوية": [("فقدان وزن رغم الأكل", 3), ("إسهال", 2), ("شحوب الأغشية المخاطية", 2), ("انتفاخ بالبطن", 1)],
    "الإسهال": [("إسهال", 3), ("ضعف عام وعدم قدرة على الوقوف", 1), ("جفاف", 2)],
    "الالتهاب الرئوي": [("سعال وصعوبة تنفس", 3), ("حرارة", 2), ("إفرازات من الأنف", 2), ("ضعف عام وعدم قدرة على الوقوف", 1)],
    "التسمم الدموي المعوي": [("إسهال", 2), ("دم بالبراز", 3), ("انتفاخ بالبطن", 2), ("ضعف حاد مفاجئ", 3)],
    "الحمى القلاعية": [("تقرحات بالفم أو القوائم", 3), ("حرارة", 2), ("سيلان لعاب زائد", 3), ("عرج", 2)],
    "تعفن الظلف": [("عرج", 3), ("رائحة كريهة من الظلف", 3), ("احمرار أو تورم بين الأصابع", 2)],
    "التهاب الملتحمة": [("إفرازات من العين", 3), ("احمرار العين", 3), ("تورّم الجفن", 1)],
    "الجدري": [("بثور أو حبوب على الجلد", 3), ("حرارة", 2), ("تقرحات بالفم أو القوائم", 1)],
    "الكزاز": [("تيبّس بالعضلات وتشنجات", 3), ("صرير أسنان وصعوبة فتح الفم", 3), ("حساسية زائدة للصوت أو اللمس", 2)],
    "نقص الكالسيوم": [("ضعف عام وعدم قدرة على الوقوف", 3), ("حديث الولادة", 2), ("برودة الأطراف", 2)],
}

# عرض "إجباري" لكل مرض (بند إضافي 137) — قبل هذا البند محرك التشخيص
# الموزون (بند 127) كان يدعم `is_required`/`is_exclusionary` بالكود
# بدون أي مرض فعلياً يستخدمهما (0 من 52 مرض) — يعني مرحلة "الجزاء عند
# غياب عرض حاسم" كانت معطّلة صامتة لكل الأمراض. هذي قائمة اجتهادية
# مبنية على معرفة بيطرية عامة معروفة (العرض الأكثر تحديداً/تشخيصاً لكل
# مرض من العشرة أمراض "الأساسية" الأكثر اكتمالاً بالبيانات) — **مو
# توصية بيطرية معتمدة لمزرعتك تحديداً**، راجعها مع طبيبك وعدّلها من
# شاشة "ربط الأعراض" لو رأى تصنيفاً مختلفاً. تعمّدت استثناء "التسمم
# الدموي المعوي" — عرضه الأكيد يتفاوت بشدة بين الشكل فوق الحاد (موت
# مفاجئ بدون أعراض) والحاد (إسهال دموي)، ما فيه عرض واحد آمن يُلزَم به."""
REQUIRED_SYMPTOM_UPDATES = {
    "التهاب الضرع": "تورم أو احمرار بالضرع",
    "الجرب": "حكة وتساقط شعر",
    "الديدان المعوية": "شحوب الأغشية المخاطية",
    "الالتهاب الرئوي": "سعال وصعوبة تنفس",
    "الحمى القلاعية": "تقرحات بالفم أو القوائم",
    "تعفن الظلف": "رائحة كريهة من الظلف",
    "الجدري": "بثور أو حبوب على الجلد",
    "الكزاز": "تيبّس بالعضلات وتشنجات",
    "نقص الكالسيوم": "حديث الولادة",
}

# عرض "إجباري" اجتهادي لبقية أمراض DISEASE_LIBRARY_V2 (بند إضافي،
# تكملة 137) — نفس منطق REQUIRED_SYMPTOM_UPDATES فوق بس لتغطية الـ40
# مرض المتبقية اللي دخلت بالمكتبة الموسّعة ولها DiseaseType مستقل (مو
# مرتبطة بـDISEASE_ALIAS_MAP بأحد الأمراض الأساسية التسعة). **اجتهادية
# مبنية على معرفة بيطرية عامة معروفة، مو توصية معتمدة لمزرعتك تحديداً
# — راجعها مع طبيبك.** تعمّدت استثناء "التسمم بالنباتات السامة" لنفس
# سبب استثناء "التسمم الدموي المعوي" بالقائمة الأولى: الأعراض تتفاوت
# بشدة حسب نوع النبات المتناول، ما فيه عرض واحد آمن يُلزَم به.
REQUIRED_SYMPTOM_UPDATES_V2 = {
    "طاعون المجترات الصغيرة (PPR)": "تقرحات بيضاء داخل الفم ورائحة كريهة",
    "داء المتدثرات / الإجهاض المعدي (Chlamydiosis)": "إجهاض في الشهرين الأخيرين من الحمل",
    "مرض السل الكاذب / الهزل (Caseous Lymphadenitis)": "خراجات ممتلئة بصديد أخضر شبيه بالجبن",
    "حمى الضأن / التسمم الدموي البكتيري (Pasteurellosis)": "موت مفاجئ مع خروج رغوة مدمية من الأنف",
    "داء الكلب المستخف / السعار (Rabies)": "تغيرات سلوكية وحركات عصبية وعدوانية",
    "القمل وذباب الجلد (Lice & Ked Infestation)": "رؤية الطفيليات بالعين المجردة بين الصوف",
    "داء النغف / الدود الجروحي (Myiasis / Screwworm)": "رؤية يراد والدود يتغذى داخل الجرح",
    "الديدان الكبدية (Fascioliasis / Liver Fluke)": "انتفاخ رخو تحت الفك السفلي (Bottle Jaw)",
    "داء الكوكيديا / إسهال الصخال (Coccidiosis)": "إسهال أسود أو مدمى في المواليد والصخال بعمر (3-8 أسابيع)",
    "طفيليات الدم / النغار (Babesiosis / Theileriosis)": "بول مدمى أو بني داكن أحمر",
    "مرض آنابلازما (Anaplasmosis)": "فقر دم حاد (بياض شاحب في العين واللثة) بدون بول مدمى",
    "نقص المغنيسيوم / كزاز الربيع (Grass Tetany)": "تشنجات عضلية حادة ورعشة بالوجه والجسم",
    "مرض العضلة البيضاء / نقص فيتامين هـ وسيلينيوم (White Muscle)": "شلال أو عرج في المواليد الحديثة وتيبس الأرجل",
    "تسمم الحمل / كيتوزيز الأمهات (Pregnancy Toxemia)": "انبعاث رائحة أسيتون (تفاح فاسد) من الفم",
    "نقص فيتامين ب1 / التلين الدماغي (Polioencephalomalacia)": "دوران الحيوان حول نفسه والرفع الرأس للأعلى (Star Gazing)",
    "النفاخ الحاد (Bloat / Tympany)": "انتفاخ شديد وبروز الخاصرة اليسرى للكرش كالكورة",
    "التسمم بالنترات / العلف الفاسد (Nitrate Poisoning)": "تغير لون الدم إلى البني الداكن (لغة الشوكولاتة)",
    "التسمم بالنحاس (Copper Toxicity)": "بول أحمر غامق إلى أسود",
    "إكزيما الإضاءة / الحساسية الضوئية (Photosensitization)": "تورم وتقشر واحمرار الجلد الخالي من الصوف (الأذن/الوجه)",
    "عسر الولادة وتداخل الأجنة (Dystocia)": "طلوق مستمرة لأكثر من ساعتين دون خروج الجنين",
    "انقلاب الرحم / انزلاق المهبل (Prolapse)": "خروج كتلة حمراء كبيرة من فتحة الحياء خلف الحيوان",
    "التهاب الرحم الصديدي (Metritis)": "خروج إفرازات رحيمة كريهة الرائحة ذات لون بني أو صديدي",
    "احتباس المشيمة (Retained Placenta)": "عدم نزول المشيمة (السلا) بعد 12 ساعة من الولادة",
    "التهاب العين الساري / الرمد (Pink Eye / Keratoconjunctivitis)": "عكورة في القرنية وتكون غشاوة بيضاء أو قرحة",
    "مرض السرع / الأكثيما المعدية (Orf / Contagious Ecthyma)": "قشور سميكة وثآليل سوداء على الشفتين وفتحات الأنف",
    "داء البروسيلاب / الحمى مالطية (Brucellosis)": "إجهاض جماعي في المراح في أواخر الحمل (الشهر 4)",
    "الداء الليستيري / مرض الدوران (Listeriosis)": "شلال نصف الوجه (تدلي الأذن والجفن وشفة واحدة)",
    "التهاب المفاصل الفيروسي (CAE / Arthritis)": "تورم وتصلب المفاصل خاصة مفصل الركبة",
    "التسمم الزئبقي / المبيدات (Pesticide Toxicity)": "تشنجات عضلية حدقة العين ضيقة جداً (Pinpoint)",
    "تسمم الرصاص (Lead Poisoning)": "عمى ناجم عن الجهاز العصبي صرير الأسنان",
    "لقمة الكرش / انسداد الكرش بالتصاق الأجسام الغريبة": "انقطاع المجش والتبرز كلياً أو روث قليل جداً",
    "حمى الوادي المتنقل / الفيروسية (Rift Valley Fever)": "إجهاض جماعي ومباغت للأمهات",
    "اليرقان الشحوبي / أنيميا الطفيليات (Anemic Jaundice)": "اصفرار ولون باهت شاحب بياض العين واللثة",
    "انسداد مجرى البول في الفحول (Urinary Calculi)": "تحذيق وصعوبة وتبول قطرات دم أو انقطاع البول",
    "التهاب الأذن الداخلية / توازن الأذن (Otitis Media)": "ميلان الرأس لجهة واحدة بوضوح شديد",
    "حمى القش / الحساسية التنفسية (Hay Fever)": "عطاس مستمر ورشح مائي شفاف من الأنف",
    "داء المشعرات الرحمي (Trichomoniasis)": "شبق وتكرار تفويت دورة الشياع وعدم مسك الحمل",
    "السالمونيلا / إسهال المواليد (Salmonellosis)": "إسهال مائي شديد لونه أصفر أو أخضر كريه جداً",
    "ورم الفك / الفك الخشبي (Actinomycosis / Lumpy Jaw)": "انتفاخ وتورم صلب صخري غير مؤلم في عظام الفك",
}

# قائمة أعراض الطوارئ الأولية (بند إضافي 127، المرحلة 4) — قائمة أسماء
# صريحة معتمَدة، تُبذر مرة وحدة هنا ثم تُدار بالكامل من الواجهة
# (`/health/emergency-symptoms`) بعدها. كل عرض جديد يشغّل عزلاً
# تلقائياً فوراً لو دخل بشجرة المساعد التشخيصي.
DEFAULT_EMERGENCY_SYMPTOMS = [
    {
        "symptom": "عمى مفاجئ / عتامة العين",
        "severity": "شديدة",
        "differential": "اشتباه ليستريا / نقص فيتامين B1 (PEM) / التهاب ملتحمة معدٍ (Pinkeye)",
        "advice": "راجع الفحص البيطري الفوري (حرارة، توازن، ردة فعل الحدقة) والسجل العلفي (تغيّر مفاجئ بالعليقة يرفع اشتباه PEM).",
    },
    {
        "symptom": "إسهال مدمى حاد",
        "severity": "حرجة",
        "differential": "اشتباه تسمم دموي معوي (Enterotoxemia) / كوكسيديا حادة / سالمونيلا",
        "advice": "فحص بيطري عاجل + عزل فوري لخطر انتقال العدوى + مراقبة الجفاف الشديد ومحلول إلكتروليت فوري.",
    },
    {
        "symptom": "إجهاض مفاجئ",
        "severity": "حرجة",
        "differential": "اشتباه بروسيلا / كلاميديا (إجهاض معدي) / حمى الوادي المتصدع",
        "advice": "عزل فوري + تعامل آمن مع الجنين والمشيمة (قفازات، حرق أو ردم صحي) + تقييم بيطري لعينة قبل أي تصرّف.",
    },
]


def register_cli(app):
    @app.cli.command("reset-password")
    @click.argument("phone")
    @click.argument("new_password")
    def reset_password(phone, new_password):
        """إعادة تعيين كلمة مرور أي حساب (يشمل حساب المالك نفسه) —
        بند إضافي 88، نقطة 3 من التحليل الثاني. النظام ما فيه بريد
        إلكتروني أصلاً (تسجيل الدخول برقم الجوال بس)، فما فيه معنى
        لخطوة "استرجاع عبر إيميل" — البديل هذا الأمر، يُشغَّل من تبويب
        Shell بلوحة Render مباشرة، بدون أي بنية بريد جديدة.
        يصفّر أيضاً قفل بند 86 (failed_login_attempts/locked_until)
        عشان الحساب يرجع يشتغل فوراً بعد التغيير."""
        user = User.query.filter_by(phone=phone).first()
        if not user:
            click.echo(f"ما فيه حساب برقم الجوال: {phone}")
            return
        user.set_password(new_password)
        user.failed_login_attempts = 0
        user.locked_until = None
        db.session.commit()
        click.echo(f"تم تغيير كلمة مرور {user.name} ({phone}) بنجاح.")

    @app.cli.command("seed")
    def seed():
        """تهيئة النظام أول مرة: الصلاحيات، الأدوار الافتراضية، حساب المالك، والخدمات."""

        # 1) الصلاحيات
        code_to_permission = {}
        for code, description in PERMISSIONS:
            perm = Permission.query.filter_by(code=code).first()
            if not perm:
                perm = Permission(code=code, description=description)
                db.session.add(perm)
            code_to_permission[code] = perm
        db.session.flush()

        # 2) الأدوار الافتراضية
        owner_role = None
        for name, cfg in DEFAULT_ROLES.items():
            role = Role.query.filter_by(name=name).first()
            if not role:
                role = Role(name=name, display_name=cfg["display_name"], is_system=cfg["is_system"])
                db.session.add(role)
                db.session.flush()
            role.permissions = [code_to_permission[c] for c in cfg["permissions"]]
            if name == "owner":
                owner_role = role
        db.session.commit()

        # 3) أول حساب مالك
        owner_phone = app.config["OWNER_PHONE"]
        if not User.query.filter_by(phone=owner_phone).first():
            owner = User(
                name=app.config["OWNER_NAME"],
                phone=owner_phone,
                role_id=owner_role.id,
                language="ar",
            )
            owner.set_password(app.config["OWNER_PASSWORD"])
            db.session.add(owner)
            click.echo(f"تم إنشاء حساب المالك برقم جوال: {owner_phone}")
        else:
            click.echo("حساب المالك موجود مسبقاً، تم تخطيه.")

        # 4) الخدمات الاختيارية (كلها موقوفة افتراضياً)
        for key, name, note in DEFAULT_SERVICES:
            if not ServiceToggle.query.filter_by(key=key).first():
                db.session.add(ServiceToggle(key=key, name=name, requirements_note=note, is_enabled=False))

        # 5) قائمة الأمراض الشائعة (أسماء فقط، بدون علاج أو جرعة)
        for name in DEFAULT_DISEASE_TYPES:
            if not DiseaseType.query.filter_by(name=name).first():
                db.session.add(DiseaseType(name=name))
        db.session.commit()

        # 6) شجرة القرار التشخيصية (بند إضافي، 2026-07-24) — أعراض +
        # روابطها بالأمراض الشائعة أعلاه.
        symptom_by_name = {}
        for name in DEFAULT_SYMPTOMS_PRIMARY:
            s = Symptom.query.filter_by(name=name).first()
            if not s:
                s = Symptom(name=name, is_primary=True)
                db.session.add(s)
            symptom_by_name[name] = s
        for links in DISEASE_SYMPTOMS.values():
            for symptom_name, _weight in links:
                if symptom_name not in symptom_by_name:
                    s = Symptom.query.filter_by(name=symptom_name).first()
                    if not s:
                        s = Symptom(name=symptom_name, is_primary=False)
                        db.session.add(s)
                    symptom_by_name[symptom_name] = s
        db.session.flush()

        for disease_name, links in DISEASE_SYMPTOMS.items():
            disease_type = DiseaseType.query.filter_by(name=disease_name).first()
            if not disease_type:
                continue
            for symptom_name, weight in links:
                symptom = symptom_by_name[symptom_name]
                exists = DiseaseSymptomLink.query.filter_by(
                    disease_type_id=disease_type.id, symptom_id=symptom.id
                ).first()
                if not exists:
                    db.session.add(DiseaseSymptomLink(
                        disease_type_id=disease_type.id, symptom_id=symptom.id, weight=weight,
                    ))

        # عرض "إجباري" اجتهادي للأمراض الأساسية (بند إضافي 137) —
        # idempotent: يحدّث `is_required=True` بس على رابط موجود أصلاً
        # (من الحلقة فوق)، ما ينشئ رابطاً جديداً ولا يلمس رابط ثانٍ.
        for disease_name, symptom_name in REQUIRED_SYMPTOM_UPDATES.items():
            disease_type = DiseaseType.query.filter_by(name=disease_name).first()
            symptom = Symptom.query.filter_by(name=symptom_name).first()
            if not disease_type or not symptom:
                continue
            link = DiseaseSymptomLink.query.filter_by(
                disease_type_id=disease_type.id, symptom_id=symptom.id,
            ).first()
            if link and not link.is_required:
                link.is_required = True

        # قوالب المهام اليومية الافتراضية (بند إضافي 107)
        if not DailyTaskTemplate.query.first():
            for order, (title, notes) in enumerate(DEFAULT_DAILY_TASK_TEMPLATES):
                db.session.add(DailyTaskTemplate(title=title, notes=notes, sort_order=order))

        db.session.commit()

        # 7) مكتبة الأمراض الموسّعة (بند إضافي 127، تكملة) — تدمج بأمراض
        # موجودة أصلاً حسب DISEASE_ALIAS_MAP، أو تنشئ مرض جديد. بيانات
        # الدواء/الجرعة تُخزَّن كنص مرجعي بـ`notes` فقط (راجع التوثيق
        # بأعلى app/disease_library_data.py لسبب عدم إنشاء TreatmentProtocol
        # تلقائياً). كل خطوة idempotent — إعادة تشغيل seed ما تكرر شي.
        for entry in DISEASE_LIBRARY_V2:
            target_name = DISEASE_ALIAS_MAP.get(entry["disease_name"], entry["disease_name"])
            disease = DiseaseType.query.filter_by(name=target_name).first()
            med_note = (
                f"دواء مرجعي: {entry['medication_name']}\n"
                f"الجرعة المرجعية: {entry['standard_dosage_note']}\n"
                f"طريقة الإعطاء: {entry['administration_route']}\n"
                f"فترة السحب: {entry['withdrawal_period']}\n"
                + "\n".join(f"• {i}" for i in entry["operational_instructions"])
            )
            if not disease:
                disease = DiseaseType(name=target_name, notes=med_note)
                db.session.add(disease)
                db.session.flush()
            elif not disease.notes:
                disease.notes = med_note

            for sym in entry["symptoms"]:
                symptom = Symptom.query.filter_by(name=sym["name"]).first()
                if not symptom:
                    symptom = Symptom(name=sym["name"], is_primary=False)
                    db.session.add(symptom)
                    db.session.flush()
                link_exists = DiseaseSymptomLink.query.filter_by(
                    disease_type_id=disease.id, symptom_id=symptom.id,
                ).first()
                if not link_exists:
                    db.session.add(DiseaseSymptomLink(
                        disease_type_id=disease.id, symptom_id=symptom.id,
                        weight=min(3, sym["weight"]),
                    ))
        db.session.commit()

        # عرض "إجباري" اجتهادي لبقية الأمراض (بند إضافي، تكملة 137) —
        # idempotent مثل تحديث الأمراض الأساسية فوق: يحدّث is_required=True
        # بس على رابط موجود أصلاً من الحلقة اللي فوق، ما ينشئ رابطاً جديداً.
        for disease_name, symptom_name in REQUIRED_SYMPTOM_UPDATES_V2.items():
            target_name = DISEASE_ALIAS_MAP.get(disease_name, disease_name)
            disease_type = DiseaseType.query.filter_by(name=target_name).first()
            symptom = Symptom.query.filter_by(name=symptom_name).first()
            if not disease_type or not symptom:
                continue
            link = DiseaseSymptomLink.query.filter_by(
                disease_type_id=disease_type.id, symptom_id=symptom.id,
            ).first()
            if link and not link.is_required:
                link.is_required = True
        db.session.commit()

        # 8) قائمة أعراض الطوارئ الأولية (بند إضافي 127، المرحلة 4) —
        # idempotent (يتفادى تكرار نفس العرض)، تعديل/إضافة بعدها من
        # `/health/emergency-symptoms` مباشرة بدون كود.
        for entry in DEFAULT_EMERGENCY_SYMPTOMS:
            symptom = Symptom.query.filter_by(name=entry["symptom"]).first()
            if not symptom:
                symptom = Symptom(name=entry["symptom"], is_primary=True)
                db.session.add(symptom)
                db.session.flush()
            if not EmergencySymptom.query.filter_by(symptom_id=symptom.id).first():
                db.session.add(EmergencySymptom(
                    symptom_id=symptom.id, severity=entry["severity"],
                    differential=entry["differential"], advice=entry["advice"],
                ))
        db.session.commit()

        click.echo("تمت التهيئة بنجاح.")
