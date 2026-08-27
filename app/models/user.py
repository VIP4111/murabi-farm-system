from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    # رقم الجوال هو المعرّف الأساسي لتسجيل الدخول (أنسب من إيميل لعمال المزرعة)
    phone = db.Column(db.String(32), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    role = db.relationship("Role", back_populates="users")

    # لغة واجهة هذا المستخدم تحديداً (مهم لواجهة العامل متعددة اللغات)
    language = db.Column(db.String(8), default="ar", nullable=False)

    # الوضع الليلي/النهاري لهذا المستخدم تحديداً (بند إضافي 158) — نفس
    # فلسفة `language` بالضبط: تفضيل شخصي محفوظ لكل حساب، يبدّله كل
    # مستخدم لنفسه من قائمة الإعدادات الجانبية بدون صلاحية خاصة.
    theme = db.Column(db.String(8), default="light", nullable=False)

    # مستوى تبسيط الواجهة (بند إضافي 225) — نفس فلسفة `theme`/`language`
    # بالضبط: تفضيل شخصي محفوظ لكل حساب. "normal" = اللوحة الكاملة
    # الحالية. "simple" = واجهة "بسيط جداً" (أزرار كبيرة، سؤال وحد
    # بالمرة) بدل اللوحة العادية عند الدخول — نفس البيانات ونفس
    # الحفظ بالضبط، بس بأقل تفاصيل ممكنة بالشاشة.
    ui_level = db.Column(db.String(8), default="normal", nullable=False)

    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=_now)

    # قفل بعد محاولات دخول فاشلة متكررة (بند إضافي 86، 2026-08-02) —
    # ما فيه أي حد سابق لعدد المحاولات، يعني أي حد يقدر يجرّب كلمات مرور
    # بلا نهاية على أي رقم جوال. 5 محاولات فاشلة متتالية = قفل 15 دقيقة.
    # يُصفَّر عند أول دخول ناجح.
    failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime, nullable=True)

    # معرّف محادثة تيليجرام لإشعارات فورية مجانية (بند إضافي 157) —
    # يحصّله المستخدم بنفسه بمراسلة بوت المزرعة على تيليجرام، ويُدخَل
    # هنا من شاشة تعديل عضو الفريق. فاضي = بدون إشعارات لهذا المستخدم
    # (صفر كسر — كل الإرسال يتجاهل المستخدمين بدون معرّف بصمت).
    telegram_chat_id = db.Column(db.String(40), nullable=True)

    # بريد إلكتروني لاستقبال التقرير اليومي التلقائي (بند إضافي 160،
    # المرحلة ج) — نفس فلسفة telegram_chat_id بالضبط: اختياري تماماً،
    # فاضي = بدون تقارير بريد لهذا المستخدم، صفر كسر بالنظام.
    email = db.Column(db.String(120), nullable=True)

    # راتب أساسي ثابت (بند إضافي 241) — نقطة بداية نظام الرواتب الشهري
    # العام. اختياري، فاضي = عضو ما فيه راتب مسجَّل بعد (ما يظهر بشاشة
    # الرواتب لين يُعبَّى). يعدّله صاحب الحلال أو المحاسب (صلاحية
    # team.manage_salary منفصلة عمداً عن users.manage الكاملة — المحاسب
    # ما يحتاج يقدر يغيّر الدور أو كلمة المرور، بس الراتب).
    base_salary = db.Column(db.Float, nullable=True)

    # بيانات هوية العامل لمسير الراتب الرسمي (بند إضافي 243) — كلها
    # اختيارية، تُدخَل يدوياً مرة وحدة (نفس شاشة الرواتب الأساسية)
    # وتُستخدم تلقائياً بكل وصل راتب بعدها.
    nationality = db.Column(db.String(80), nullable=True)
    passport_number = db.Column(db.String(40), nullable=True)
    border_number = db.Column(db.String(40), nullable=True)
    payment_method = db.Column(db.String(40), nullable=True)

    # تاريخ وصول العامل للسعودية (بند إضافي 247، طلبك الصريح) — أساس
    # حساب الراتب المتناسب بأيام الحضور الفعلية كل شهر (نفس شاشة
    # الرواتب الأساسية). اختياري — فاضي يعني الراتب يُحسب كامل بدون
    # تناسب (سلوك ما قبل هذا البند، بدون تغيير على عمّال ما سُجِّل
    # لهم تاريخ وصول).
    saudi_arrival_date = db.Column(db.Date, nullable=True)

    # دليل المربي المبتدئ ومحرك التوجيه اليومي (بند إضافي 168) — وسم
    # مستقل عن الدور الوظيفي (role_id): مالك أو عامل ممكن يكون مبتدئاً
    # فعلياً بغض النظر عن صلاحياته. يُضبط باختيار المستخدم نفسه بمسار
    # الترحيب أول دخول، أو يعدّله لاحقاً من إعدادات حسابه.
    is_beginner = db.Column(db.Boolean, default=False, nullable=False)
    onboarding_completed_at = db.Column(db.DateTime, nullable=True)

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    LOCKOUT_THRESHOLD = 5
    LOCKOUT_MINUTES = 15

    @staticmethod
    def _now_naive_utc():
        # SQLite يخزّن DateTime بدون معلومة المنطقة الزمنية (naive) — لازم
        # نقارن بنفس النوع، وإلا TypeError عند المقارنة (aware مقابل naive).
        # عمداً منفصلة عن _now() المشترَكة (تُستخدم لأعمدة تُعرَض بس، مو تُقارَن).
        return datetime.now(timezone.utc).replace(tzinfo=None)

    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > self._now_naive_utc())

    def register_failed_login(self) -> None:
        from datetime import timedelta
        self.failed_login_attempts = (self.failed_login_attempts or 0) + 1
        if self.failed_login_attempts >= self.LOCKOUT_THRESHOLD:
            self.locked_until = self._now_naive_utc() + timedelta(minutes=self.LOCKOUT_MINUTES)

    def register_successful_login(self) -> None:
        self.failed_login_attempts = 0
        self.locked_until = None

    # Flask-Login يحتاج is_active (اسم مختلف عن حقلنا is_active_account)
    @property
    def is_active(self):
        return self.is_active_account

    def has_permission(self, code: str) -> bool:
        return self.role is not None and self.role.has_permission(code)

    def __repr__(self):
        return f"<User {self.name} ({self.role.name if self.role else '-'})>"
