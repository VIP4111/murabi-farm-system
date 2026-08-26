"""تحليل موسمية أسعار البيع بالتقويم الهجري (بند إضافي 255، طلبك
الصريح بعد نقاش عن أفضل وقت للبيع): بدل الاعتماد على شهر ميلادي ثابت
(عيد الأضحى يتحرك ~11 يوم كل سنة ميلادية)، التحليل مبني على الشهر
الهجري — رمضان (9) وذو الحجة (12، فيه عيد الأضحى) هما الموسمان
الدينيان المؤثّران فعلياً بسوق الأغنام/الماعز بالسعودية.

**مبدأ أساسي، بطلبك الصريح**: صفر بيانات مختلَقة. ما فيه اتصال بسوق
خارجي ولا سعر "متوقّع" مبني على تخمين — كل رقم بهذا التحليل مشتق
مباشرة من عمليات بيع حقيقية سجَّلتها المزرعة (`Finance`،
`operation_type='sale'`). "الخط الموسمي" هو متوسط أسعار بيعك الحقيقية
بنفس الشهر الهجري عبر كل السنين اللي عندك بيانات فيها — قاعدة بيانات
تكبر تلقائياً كل موسم بيع جديد، بدون أي تدخل يدوي."""
from datetime import date
from hijridate import Gregorian
from app.models import Finance

HIJRI_MONTH_NAMES_AR = [
    "", "محرم", "صفر", "ربيع الأول", "ربيع الآخر", "جمادى الأولى", "جمادى الآخرة",
    "رجب", "شعبان", "رمضان", "شوّال", "ذو القعدة", "ذو الحجة",
]

RELIGIOUS_SEASON_MONTHS = {9, 12}  # رمضان، ذو الحجة (فيه عيد الأضحى)

MIN_YEARS_FOR_RELIABLE_PATTERN = 2


def _to_hijri(d: date) -> tuple[int, int]:
    h = Gregorian(d.year, d.month, d.day).to_hijri()
    return h.year, h.month


def seasonal_price_analysis() -> dict:
    today_hy, _ = _to_hijri(date.today())

    sales = Finance.query.filter(
        Finance.operation_type == "sale", Finance.is_cancelled.is_(False),
    ).all()

    by_month_all: dict[int, list[float]] = {m: [] for m in range(1, 13)}
    by_month_current_year: dict[int, list[float]] = {m: [] for m in range(1, 13)}
    years_seen: set[int] = set()

    for row in sales:
        hy, hm = _to_hijri(row.date)
        years_seen.add(hy)
        by_month_all[hm].append(row.amount)
        if hy == today_hy:
            by_month_current_year[hm].append(row.amount)

    months = []
    for m in range(1, 13):
        hist_prices = by_month_all[m]
        cur_prices = by_month_current_year[m]
        months.append({
            "hijri_month": m,
            "month_name": HIJRI_MONTH_NAMES_AR[m],
            "is_religious_season": m in RELIGIOUS_SEASON_MONTHS,
            "current_year_avg": round(sum(cur_prices) / len(cur_prices), 2) if cur_prices else None,
            "current_year_count": len(cur_prices),
            "historical_avg": round(sum(hist_prices) / len(hist_prices), 2) if hist_prices else None,
            "historical_count": len(hist_prices),
        })

    return {
        "months": months,
        "data_years_count": len(years_seen),
        "sufficient_data": len(years_seen) >= MIN_YEARS_FOR_RELIABLE_PATTERN,
        "total_sales_count": len(sales),
        "current_hijri_year": today_hy,
    }
