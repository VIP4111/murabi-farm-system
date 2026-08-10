from datetime import datetime, timezone
from flask_babel import lazy_gettext as _l
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class Warehouse(db.Model):
    """موقع تخزين فعلي (بند إضافي 52، جزء 3) — طبقة إضافية فوق الإجمالي
    الحالي (`Feed.available_qty` / `Pharmacy.available_qty`، اللي يبقى
    المرجع الصحيح دائماً بلا أي تعديل عليه — قرارك الصريح). المستودع
    الافتراضي (`is_default=True`) يمثّل "الرصيد العام غير المُوزَّع"
    ويُحتسب ضمنياً (الإجمالي ناقص كل المستودعات الأخرى المسمّاة)، مو
    مخزَّناً كصف قاعدة بيانات — فأي عملية إدخال/خصم موجودة أصلاً
    بالنظام (حركة علف، استخدام دواء بعلاج...) تبقى شغّالة بلا أي
    تعديل، وتنعكس تلقائياً بالمستودع الافتراضي بدون أي كود إضافي.
    التوزيع الفعلي على مستودعات مسمّاة (صيدلية فرعية، حظيرة تغذية
    مباشرة...) يصير فقط عبر `warehouse_service.transfer_stock` الصريح."""
    __tablename__ = "warehouses"

    WAREHOUSE_TYPES = ["feed", "pharmacy", "mixed"]
    WAREHOUSE_TYPE_LABELS_AR = {"feed": _l("علف"), "pharmacy": _l("صيدلية"), "mixed": _l("مختلط")}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    warehouse_type = db.Column(db.String(16), nullable=False)
    location_note = db.Column(db.String(255))
    is_default = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=_now)


class FeedWarehouseStock(db.Model):
    """رصيد علف مسمّى محفوظ بمستودع غير افتراضي — لا يُنشأ صف إلا عبر
    `transfer_stock` (تحويل صريح)، ومجموع كل الصفوف لعلف معيّن لازم
    يبقى ≤ `Feed.available_qty` دائماً."""
    __tablename__ = "feed_warehouse_stock"

    id = db.Column(db.Integer, primary_key=True)
    feed_id = db.Column(db.Integer, db.ForeignKey("feeds.id"), nullable=False)
    feed = db.relationship("Feed")
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False)
    warehouse = db.relationship("Warehouse")
    qty = db.Column(db.Float, default=0, nullable=False)

    __table_args__ = (db.UniqueConstraint("feed_id", "warehouse_id", name="uq_feed_warehouse"),)


class PharmacyWarehouseStock(db.Model):
    """نفس `FeedWarehouseStock` بالضبط لكن لأصناف الصيدلية."""
    __tablename__ = "pharmacy_warehouse_stock"

    id = db.Column(db.Integer, primary_key=True)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey("pharmacy.id"), nullable=False)
    pharmacy = db.relationship("Pharmacy")
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False)
    warehouse = db.relationship("Warehouse")
    qty = db.Column(db.Float, default=0, nullable=False)

    __table_args__ = (db.UniqueConstraint("pharmacy_id", "warehouse_id", name="uq_pharmacy_warehouse"),)
