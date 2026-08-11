from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class Asset(db.Model):
    """أصل ثابت بالمزرعة يحتاج صيانة دورية (بند إضافي 186) — مظلة،
    مولّد، سقاية آلية، مضخة مياه... **منفصل عمداً عن `Equipment`**:
    Equipment مخزون قابل للاستهلاك/الاستعارة (رصيد يتحرك)، هذا أصل
    واحد ثابت له جدول صيانة دوري خاص به، مفهوم مختلف تماماً."""
    __tablename__ = "assets"

    CATEGORIES = ["shade", "generator", "waterer", "pump", "other"]

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(32), default="other", nullable=False)
    barn_id = db.Column(db.Integer, db.ForeignKey("barns.id"), nullable=True)
    barn = db.relationship("Barn")

    # صفر = بدون صيانة دورية مجدولة (بعض الأصول ما تحتاج، توثيق بس)
    maintenance_interval_days = db.Column(db.Integer, nullable=True)
    last_maintenance_date = db.Column(db.Date, nullable=True)

    status = db.Column(db.String(16), default="active", nullable=False)  # active / retired
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)


class AssetMaintenanceLog(db.Model):
    __tablename__ = "asset_maintenance_logs"

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("assets.id"), nullable=False)
    asset = db.relationship("Asset")
    date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text)
    cost = db.Column(db.Float, nullable=True)
    performed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    performed_by = db.relationship("User")
    created_at = db.Column(db.DateTime, default=_now)


class UtilityReading(db.Model):
    """قراءة استهلاك دوري للطاقة/الماء (بند إضافي 186) — تسجيل يدوي
    بسيط (لا عدادات ذكية متصلة)، الهدف كشف تغيّر مفاجئ (تسريب،
    مولّد يستهلك أكثر من المعتاد) بمقارنة القراءات مع الوقت."""
    __tablename__ = "utility_readings"

    UTILITY_TYPES = ["water", "electricity"]

    id = db.Column(db.Integer, primary_key=True)
    utility_type = db.Column(db.String(16), nullable=False)
    date = db.Column(db.Date, nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(16))  # m3 / kWh
    cost = db.Column(db.Float, nullable=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)
