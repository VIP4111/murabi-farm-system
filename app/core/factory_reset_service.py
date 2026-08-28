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
from app.extensions import db
from app.models import User


def _preserve_owner_snapshot(user: User) -> dict:
    return {
        "name": user.name,
        "phone": user.phone,
        "password_hash": user.password_hash,
        "language": user.language,
    }


def factory_reset(*, current_user: User, app) -> dict:
    """يرجّع dict فيه عدد الصفوف المحذوفة لكل جدول. يستدعي أمر
    `flask seed` نفسه (عبر Click، بدون تكرار منطقه) داخل نفس الطلب."""
    snapshot = _preserve_owner_snapshot(current_user)

    counts = {}
    for table in reversed(db.metadata.sorted_tables):
        result = db.session.execute(table.delete())
        if result.rowcount:
            counts[table.name] = result.rowcount
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
