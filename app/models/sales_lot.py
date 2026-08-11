"""صانع مجموعات البيع الذكي (بند إضافي 191) — تجميع رؤوس محدَّدة
"دفعة بيع" واحدة، مع رابط عام (بدون تسجيل دخول) يعرض بروفايل تجاري
احترافي للمشتري المحتمل. نفس فلسفة `FarmSettings.sales_catalog_token`
بالضبط (بند 185) — رمز عشوائي طويل، صفر بيانات حساسة بالصفحة العامة."""
import secrets
from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


def _new_token() -> str:
    return secrets.token_urlsafe(24)


class SalesLot(db.Model):
    __tablename__ = "sales_lots"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    notes = db.Column(db.Text)
    target_amount = db.Column(db.Float)  # هدف مالي اختياري (بند إضافي 191.2)
    share_token = db.Column(db.String(64), unique=True, nullable=False, default=_new_token)
    status = db.Column(db.String(16), default="open", nullable=False)  # open/sold/archived

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_by = db.relationship("User")
    created_at = db.Column(db.DateTime, default=_now)

    items = db.relationship("SalesLotItem", backref="lot", cascade="all, delete-orphan")


class SalesLotItem(db.Model):
    __tablename__ = "sales_lot_items"

    id = db.Column(db.Integer, primary_key=True)
    lot_id = db.Column(db.Integer, db.ForeignKey("sales_lots.id"), nullable=False, index=True)
    animal_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=False, index=True)
    animal = db.relationship("Animal")

    __table_args__ = (db.UniqueConstraint("lot_id", "animal_id", name="uq_sales_lot_animal"),)
