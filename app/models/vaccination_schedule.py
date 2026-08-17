"""
تقويم التحصينات (بند إضافي 63، 2026-07-28) — جدولة تحصين جماعي مستقبلي
لحظيرة كاملة (حظيرة + لقاح + تاريخ مخطَّط)، مفهوم جديد كلياً منفصل عن
`Vaccination.next_due_date` (اللي يُحسب بعد ما رأس معيّن يتحصّن فعلياً،
مو قبلها). عدد الرؤوس المستهدف **ما يُخزَّن أبداً** — يُحسب حياً دائماً
من `Animal.query.filter_by(barn_id=..., status="active").count()` (نفس
النمط المستخدم أصلاً بـ`context_service.py`)، عشان يعكس واقع الحظيرة
الفعلي وقت العرض، حتى لو دخلت/خرجت رؤوس بعد الجدولة.
"""
from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class VaccinationSchedule(db.Model):
    __tablename__ = "vaccination_schedules"

    STATUSES = ["scheduled", "completed", "cancelled"]

    id = db.Column(db.Integer, primary_key=True)

    barn_id = db.Column(db.Integer, db.ForeignKey("barns.id"), nullable=False)
    barn = db.relationship("Barn")

    pharmacy_id = db.Column(db.Integer, db.ForeignKey("pharmacy.id"), nullable=False)
    pharmacy = db.relationship("Pharmacy")

    planned_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default="scheduled", nullable=False)
    notes = db.Column(db.Text)
    completed_at = db.Column(db.DateTime, nullable=True)

    # رؤوس مستهدفة محدَّدة يدوياً (بند إضافي 210) — طلبك بالنص: "أختار
    # اللي أحتاجه أحصّنه ولي ما أحتاجه ما أحط عليه علامة". فاضي = كل
    # رؤوس الحظيرة (السلوك الأصلي قبل هذا البند، `live_head_count`
    # يبقى يشتغل بلا تغيير). معبّى = أرقام IDs مفصولة بفاصلة لرؤوس
    # مختارة صراحة وقت الجدولة، تُقرَأ كصورة ثابتة — لو رأس خرج من
    # الحظيرة بعدها يبقى بالقائمة (مرجع تاريخي لما اختاره المستخدم).
    target_animal_ids = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=_now)

    def live_head_count(self) -> int:
        from app.models import Animal
        return Animal.query.filter_by(barn_id=self.barn_id, status="active").count()

    def target_animals(self):
        from app.models import Animal
        if not self.target_animal_ids:
            return Animal.query.filter_by(barn_id=self.barn_id, status="active").order_by(Animal.animal_no).all()
        ids = [int(x) for x in self.target_animal_ids.split(",") if x.strip()]
        return Animal.query.filter(Animal.id.in_(ids)).order_by(Animal.animal_no).all()

    def target_count(self) -> int:
        if not self.target_animal_ids:
            return self.live_head_count()
        return len([x for x in self.target_animal_ids.split(",") if x.strip()])
