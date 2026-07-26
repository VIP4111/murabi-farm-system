"""
الأدوار والصلاحيات — قابلة للتوسيع بالكامل من واجهة الإعدادات.

Role: مسمى وظيفي (مالك، دكتور، عامل، أو أي مسمى جديد يضيفه صاحب الحلال).
Permission: قدرة واحدة محددة (زي "animals.manage") - القائمة الكاملة
            معرّفة بملف permissions_registry.py.
role_permissions: جدول ربط many-to-many بين الاثنين — هذا هو اللي يخلي
            الصلاحيات "بيانات" مو "كود مكتوب"، فتقدر تتغيّر وقت التشغيل.
"""
from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


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
    created_at = db.Column(db.DateTime, default=_now)

    permissions = db.relationship(
        "Permission", secondary=role_permissions, backref="roles"
    )
    users = db.relationship("User", back_populates="role")

    def has_permission(self, code: str) -> bool:
        return any(p.code == code for p in self.permissions)

    def __repr__(self):
        return f"<Role {self.name}>"
