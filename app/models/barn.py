from datetime import datetime, timezone
from flask_babel import get_locale
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class Barn(db.Model):
    __tablename__ = "barns"

    id = db.Column(db.Integer, primary_key=True)
    barn_no = db.Column(db.String(32), unique=True, nullable=False)
    barn_name = db.Column(db.String(120), nullable=False)
    # بند إضافي (2026-08-31) — طلبك الصريح بعد ما لاحظت اسم الحظيرة
    # يبقى عربياً بشاشة الدكتور الإنجليزية رغم ترجمة كل النص النظامي
    # حوله: اسم الحظيرة بيانات حرة كتبها المستخدم، ما يقدر النظام
    # "يترجمها" تلقائياً بدقة (نفس مبدأ عدم ترجمة أسماء الحيوانات/
    # العمال). الحل: حقل اختياري ثانٍ يكتبه صاحب الحلال بنفسه — لو
    # فاضي، يبقى الاسم العربي الأصلي يظهر للجميع كما كان (سلوك قديم
    # محفوظ بدون كسر).
    barn_name_en = db.Column(db.String(120))
    barn_type = db.Column(db.String(64))  # عادية / عزل / نفاس ... إلخ
    capacity = db.Column(db.Integer)

    # العامل المسؤول عن هالحظيرة — أساس توجيه المهام التلقائي (مرحلة 5)
    responsible_worker_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    responsible_worker = db.relationship("User")

    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)

    def display_name(self) -> str:
        """اسم الحظيرة المعروض حسب لغة المستخدم الحالي — يرجع
        `barn_name_en` لو مضبوط والمستخدم لغته غير عربية، وإلا الاسم
        العربي الأصلي (سلوك ما قبل هذا البند، محفوظ بدون كسر لمن ما
        أضاف اسماً إنجليزياً بعد)."""
        if self.barn_name_en and str(get_locale()) != "ar":
            return self.barn_name_en
        return self.barn_name

    animals = db.relationship("Animal", back_populates="barn")
    feeding_schedules = db.relationship(
        "BarnFeedingSchedule", back_populates="barn",
        order_by="BarnFeedingSchedule.sort_order", cascade="all, delete-orphan",
    )


class BarnFeedingSchedule(db.Model):
    """موعد وجبة علف واحدة لحظيرة معيّنة (بند إضافي 131) — كل حظيرة
    تحدّد عدد ومواعيد وجباتها لحالها (قرارك الصريح: إعداد مستقل لكل
    حظيرة، مو رقم عام للمزرعة). عند وصول الموعد، يولّد النظام تلقائياً
    مهمة واحدة مجمَّعة (توزيع علف + تنظيف معالف + تغيير ماء) للعامل
    المسؤول عن الحظيرة — نفس فلسفة `daily_task_service.py` بالضبط
    (idempotent عبر source_id مبني من تجزئة رقمية، بدون Cron)."""
    __tablename__ = "barn_feeding_schedules"

    id = db.Column(db.Integer, primary_key=True)
    barn_id = db.Column(db.Integer, db.ForeignKey("barns.id"), nullable=False)
    barn = db.relationship("Barn", back_populates="feeding_schedules")

    meal_time = db.Column(db.Time, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=_now)
