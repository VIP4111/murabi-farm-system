"""
الأدوار والصلاحيات — قابلة للتوسيع بالكامل من واجهة الإعدادات.

Role: مسمى وظيفي (مالك، دكتور، عامل، أو أي مسمى جديد يضيفه صاحب الحلال).
Permission: قدرة واحدة محددة (زي "animals.manage") - القائمة الكاملة
            معرّفة بملف permissions_registry.py.
role_permissions: جدول ربط many-to-many بين الاثنين — هذا هو اللي يخلي
            الصلاحيات "بيانات" مو "كود مكتوب"، فتقدر تتغيّر وقت التشغيل.
"""
from datetime import datetime, timezone
from flask_babel import lazy_gettext as _l, get_locale
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


# بند إضافي (2026-08-31) — طلبك المباشر بعد صورة شاشة "تعديل عضو":
# قائمة اختيار "الدور" كانت تعرض display_name الخام (عربي دايماً) حتى
# لحساب إنجليزي بالكامل. نفس معمارية SpeciesType بالضبط: name عمود
# داخلي ثابت (owner/doctor/worker/...) للأدوار الجاهزة الستة، فترجمته
# ممكنة بأمان — بشرط واحد إضافي هنا (مو موجود بـSpeciesType): لو صاحب
# الحلال غيّر display_name يدوياً من شاشة "تعديل صلاحيات الدور" (حقل
# قابل للتعديل حتى للأدوار الجاهزة)، التعديل اليدوي يبقى الأولوية —
# صفر ترجمة تلقائية تتجاوز اسماً كتبه المستخدم بنفسه.
_KNOWN_ROLE_LABELS = {
    "owner": (_l("صاحب الحلال"), "صاحب الحلال"),
    "doctor": (_l("الدكتور"), "الدكتور"),
    "worker": (_l("العامل"), "العامل"),
    "nurse": (_l("الممرض"), "الممرض"),
    "accountant": (_l("المحاسب"), "المحاسب"),
    "viewer": (_l("مشاهد"), "مشاهد"),
    "farm_worker": (_l("عامل زراعي"), "عامل زراعي"),
    "construction_worker": (_l("عامل بناء"), "عامل بناء"),
    "farm_manager": (_l("مدير مزرعة"), "مدير مزرعة"),
    "livestock_worker": (_l("عامل تربية مواشي"), "عامل تربية مواشي"),
}


role_permissions = db.Table(
    "role_permissions",
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id"), primary_key=True),
    db.Column("permission_id", db.Integer, db.ForeignKey("permissions.id"), primary_key=True),
)


class Permission(db.Model):
    __tablename__ = "permissions"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"<Permission {self.code}>"


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    # اسم داخلي ثابت (owner/doctor/worker/أو اسم جديد يحدده صاحب الحلال)
    name = db.Column(db.String(64), unique=True, nullable=False)
    # الاسم المعروض بالواجهة، وهذا اللي المالك يقدر يغيّره بحرية
    display_name = db.Column(db.String(120), nullable=False)
    # الأدوار الجاهزة (مالك/دكتور/عامل) is_system=True، ما تنحذف بالغلط
    is_system = db.Column(db.Boolean, default=False, nullable=False)
    # بند إضافي (2026-08-31) — خلل حقيقي: `flask seed` (يشتغل تلقائياً
    # بكل نشر على Render عبر Procfile's `release: flask db upgrade &&
    # flask seed`) كان يعيد كتابة `role.permissions` لكل الأدوار
    # الجاهزة (owner/doctor/worker/nurse/accountant/viewer) من
    # `DEFAULT_ROLES` بدون قيد — أي تعديل يدوي فعله صاحب الحلال بشاشة
    # "تعديل صلاحيات الدور" كان يُمحى بصمت عند أول نشر تالٍ. هذا العلم
    # يصير True تلقائياً بمجرد أول حفظ يدوي فعلي من `role_edit()`،
    # وseed() بعدها يتخطى إعادة الكتابة لأي دور علّمه True — يبقى
    # يزامن الأدوار اللي ما لمسها صاحب الحلال بعد مع أي صلاحية جديدة
    # تُضاف مستقبلاً بالكود.
    permissions_customized = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=_now)

    permissions = db.relationship(
        "Permission", secondary=role_permissions, backref="roles"
    )
    users = db.relationship("User", back_populates="role")

    def has_permission(self, code: str) -> bool:
        return any(p.code == code for p in self.permissions)

    def display_label(self) -> str:
        """اسم الدور المترجَم لو كان أحد الأدوار الجاهزة الستة المعروفة
        ولسا بمسمّاه الافتراضي (ما عدَّله صاحب الحلال يدوياً)، وإلا
        display_name الأصلي كما هو — بيانات حرة، صفر ترجمة تلقائية
        تتجاوز اسماً كتبه المستخدم بنفسه."""
        known = _KNOWN_ROLE_LABELS.get(self.name)
        if known and self.display_name == known[1]:
            return str(known[0])
        return self.display_name

    def __repr__(self):
        return f"<Role {self.name}>"
