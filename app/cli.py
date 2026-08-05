import click
from app.extensions import db
from app.models import Role, Permission, User, ServiceToggle, DiseaseType, Symptom, DiseaseSymptomLink, DailyTaskTemplate
from app.permissions_registry import PERMISSIONS, DEFAULT_ROLES

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

        # قوالب المهام اليومية الافتراضية (بند إضافي 107)
        if not DailyTaskTemplate.query.first():
            for order, (title, notes) in enumerate(DEFAULT_DAILY_TASK_TEMPLATES):
                db.session.add(DailyTaskTemplate(title=title, notes=notes, sort_order=order))

        db.session.commit()
        click.echo("تمت التهيئة بنجاح.")
