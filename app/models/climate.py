from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class WeatherReading(db.Model):
    """
    قراءة/توقّع طقس يومي واحد للمزرعة (موقع واحد للمزرعة كلها — بند
    إضافي 49، بقرارك الصريح). كل صف = يوم واحد، بمصدره (توقّع من
    Open-Meteo أو fallback يدوي مستقبلاً)، لتفادي استدعاء API الخارجي
    بكل تحميل صفحة ونحتفظ بتاريخ THI للربط مع استهلاك العلف (FCR).
    """
    __tablename__ = "weather_readings"

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True, index=True)

    temp_max_c = db.Column(db.Float, nullable=False)
    humidity_at_peak = db.Column(db.Float, nullable=False)
    # الرطوبة النسبية بالساعة اللي فيها أعلى حرارة باليوم — أدق لحساب
    # THI اللحظة الأخطر، بدل متوسط يومي مسطّح قد يخفي ذروة الإجهاد.

    thi = db.Column(db.Float, nullable=False)
    stress_level = db.Column(db.String(16), nullable=False)
    # normal / mild / moderate / severe / emergency — راجع
    # weather_service.classify_stress_level للحدود بالتفصيل.

    source = db.Column(db.String(20), default="open-meteo", nullable=False)
    fetched_at = db.Column(db.DateTime, default=_now, nullable=False)

    def __repr__(self):
        return f"<WeatherReading {self.date} THI={self.thi}>"
