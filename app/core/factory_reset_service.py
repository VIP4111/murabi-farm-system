"""ضبط المصنع (بند إضافي 282) — طلبك الصريح، بعد ما وضّحت إن الجلسة ما
عندها اتصال مباشر بقاعدة البيانات الحية: "سولي زر ضبط المصنع" — زر
حقيقي بشاشة الإعدادات ينفّذه المالك بنفسه على السيرفر الحي مباشرة،
بدل ما يحتاج وصول تقني مو متوفر لهذي الجلسة.

**خطر جداً — حذف نهائي وبلا رجعة.** يمسح كل جدول بقاعدة البيانات
(حيوانات، حظائر، مالية، صحة، مهام، فريق...) ثم يعيد تشغيل نفس منطق
`flask seed` (الصلاحيات + الأدوار الافتراضية الثلاثة + القوائم
المرجعية الأساسية)، وأخيراً يحافظ على حساب المالك الحالي (نفس الجوال
وكلمة المرور والاسم) عشان ما يُقفَل بره النظام بعد الحذف — بدون هذا،
`seed()` كانت تنشئ حساب مالك جديد برقم الجوال الافتراضي من `.env`
(`OWNER_PHONE`)، مختلف عن رقم المالك الفعلي غالباً."""
from sqlalchemy import text

from app.extensions import db
from app.models import User


def _preserve_owner_snapshot(user: User) -> dict:
    return {
        "name": user.name,
        "phone": user.phone,
        "password_hash": user.password_hash,
        "language": user.language,
    }


def _wipe_all_tables() -> dict:
    """يمسح كل جدول بقاعدة البيانات، بدون أي commit (المستدعي يتكفّل بها).

    **بند إضافي (2026-08-29) — إصلاح خلل حقيقي بالإنتاج**: الحذف جدول-جدول
    بترتيب `reversed(sorted_tables)` كان يعتمد ضمنياً إن قاعدة البيانات ما
    تفرض قيود المفاتيح الأجنبية بصرامة أثناء الحذف — SQLite (المستخدمة
    باختبارات pytest) فعلاً متساهلة بهذا الخصوص بشكل افتراضي، فالاختبارات
    كانت تنجح دايماً. لكن Postgres (المستخدمة فعلياً على Render) صارمة،
    وفيها جداول بعلاقة ذاتية (مثل `animals.mother_id`/`father_id` تشير
    لنفس جدول `animals`) قد ترفض ترتيب الحذف هذا وتوقف العملية بمنتصفها
    بخطأ حقيقي — النتيجة: بعض البيانات (أو كلها) تبقى، مع خروج المستخدم
    من الجلسة وكأن العملية نجحت. الحل: على Postgres نطلب من قاعدة
    البيانات نفسها تمسح كل الجداول دفعة وحدة بأمر `TRUNCATE ... CASCADE`
    (يتجاهل ترتيب الجداول تماماً، القاعدة تتولى حل الاعتماديات بنفسها).
    SQLite (تطوير/اختبار) تبقى على المنطق القديم لأنها لا تدعم CASCADE
    بنفس الطريقة."""
    counts = {}
    if db.engine.dialect.name == "postgresql":
        table_names = [t.name for t in db.metadata.sorted_tables]
        if table_names:
            quoted = ", ".join(f'"{name}"' for name in table_names)
            db.session.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))
        counts = {name: None for name in table_names}
    else:
        for table in reversed(db.metadata.sorted_tables):
            result = db.session.execute(table.delete())
            if result.rowcount:
                counts[table.name] = result.rowcount
    return counts


def factory_reset(*, current_user: User, app) -> dict:
    """يرجّع dict فيه عدد الصفوف المحذوفة لكل جدول. يستدعي أمر
    `flask seed` نفسه (عبر Click، بدون تكرار منطقه) داخل نفس الطلب."""
    snapshot = _preserve_owner_snapshot(current_user)

    counts = _wipe_all_tables()
    db.session.commit()

    from click.testing import CliRunner
    result = CliRunner().invoke(app.cli, ["seed"], standalone_mode=False)
    if result.exception:
        # ما نبتلع الخطأ — بعد حذف كل البيانات، فشل إعادة التهيئة يعني
        # نظام فاضي بلا حتى حساب دخول واحد، لازم يوصل واضح للمستخدم.
        raise RuntimeError(f"فشلت إعادة التهيئة بعد الحذف: {result.exception}") from result.exception

    owner = User.query.filter_by(phone=app.config["OWNER_PHONE"]).first()
    if owner:
        owner.name = snapshot["name"]
        owner.phone = snapshot["phone"]
        owner.password_hash = snapshot["password_hash"]
        owner.language = snapshot["language"]
        db.session.commit()

    return counts
