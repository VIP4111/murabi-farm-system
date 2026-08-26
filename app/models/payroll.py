from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class Payroll(db.Model):
    """راتب شهري لعضو فريق (بند إضافي 242) — نظام رواتب عام لكل الفريق،
    بخلاف "موظف الشهر" (بند 239، مكافأة أداء لأفضل عامل بس). كل سجل
    يمثّل راتب رأس واحد لشهر واحد، بحالة draft (تحت التجهيز، يقدر
    يتعدَّل) أو confirmed (اتحوّل فعلياً، ثابت)."""
    __tablename__ = "payroll"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    user = db.relationship("User", foreign_keys=[user_id])
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)

    # لقطة (Snapshot) وقت الإنشاء — تعديل راتب العامل الأساسي لاحقاً ما
    # يغيّر رواتب الأشهر السابقة المسجَّلة أصلاً.
    base_salary = db.Column(db.Float, nullable=False, default=0)
    bonus_amount = db.Column(db.Float, nullable=False, default=0)

    status = db.Column(db.String(24), default="draft", nullable=False)
    # draft / confirmed

    recipient_name = db.Column(db.String(120), nullable=True)
    signed_receipt_file_url = db.Column(db.String(255), nullable=True)

    finance_id = db.Column(db.Integer, db.ForeignKey("finance.id"), nullable=True)
    finance = db.relationship("Finance")

    confirmed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    confirmed_by = db.relationship("User", foreign_keys=[confirmed_by_id])
    confirmed_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=_now)

    deductions = db.relationship("PayrollDeduction", backref="payroll", cascade="all, delete-orphan")

    __table_args__ = (db.UniqueConstraint("user_id", "year", "month", name="uq_payroll_user_period"),)

    @property
    def total_deductions(self) -> float:
        return sum(d.amount for d in self.deductions)

    @property
    def net_amount(self) -> float:
        return self.base_salary + self.bonus_amount - self.total_deductions


class PayrollDeduction(db.Model):
    """سطر خصم واحد بسبب محدَّد (بند إضافي 242) — بطلبك الصريح: "إضافة
    خصم ثاني... زر يضيف سطر جديد للخصم". عدد غير محدود لكل راتب."""
    __tablename__ = "payroll_deductions"

    id = db.Column(db.Integer, primary_key=True)
    payroll_id = db.Column(db.Integer, db.ForeignKey("payroll.id"), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    reason = db.Column(db.String(200), nullable=True)


class WorkerTravelPeriod(db.Model):
    """فترة سفر عامل (بند إضافي 247، طلبك الصريح: "زر سفر اذا كان
    مسافر يتسجل مسافر بدون راتب") — `end_date=None` يعني لسا مسافر
    (الفترة مفتوحة). راتب أيام السفر يُستبعد من حساب الراتب المتناسب
    الشهري (`payroll_service.present_days_in_month`)، مو تصفير الشهر
    كامل — بحسب توضيحك: "الراتب يتقسم على أيام الشهر"."""
    __tablename__ = "worker_travel_periods"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    user = db.relationship("User", foreign_keys=[user_id])
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=_now)
