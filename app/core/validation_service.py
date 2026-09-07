"""فحوصات منطقية لسلامة الإدخال وقت الحفظ (بند إضافي 187) — بمعزل
عن `data_integrity_service.py` (يفحص بيانات موجودة أصلاً بعد الحفظ،
عرض فقط بدون منع) — هذا يمنع الخطأ **قبل** ما يوصل قاعدة البيانات
أصلاً، بنفس نمط `ValueError` المستخدَم أصلاً بكل خدمات المشروع
(`Equipment.deduct_stock`, `create_animal`...).

**حدود متعمَّدة**: القيم القصوى هنا تقريبية واسعة عمداً (نطاق واقعي
موسَّع لأغنام/ماعز بالغة، مو حد دقيق لكل عمر/سلالة) — الهدف يمنع خطأ
كتابة واضح (رقم زائد صفر، فاصلة بمكان غلط)، مو يرفض قيماً نادرة لكن
ممكنة فعلياً."""
from datetime import date
from flask_babel import gettext as _

MAX_WEIGHT_KG = {"sheep_goat": 200, "ostrich": 160}
DEFAULT_MAX_WEIGHT_KG = 200


def validate_weight(weight: float | None, species: str = "sheep_goat") -> None:
    if weight is None:
        return
    if weight <= 0:
        raise ValueError(_("الوزن لازم يكون رقماً موجباً أكبر من صفر."))
    max_weight = MAX_WEIGHT_KG.get(species, DEFAULT_MAX_WEIGHT_KG)
    if weight > max_weight:
        raise ValueError(
            _("وزن %(weight)s كجم غير منطقي — أعلى من الحد المتوقع (%(max)s كجم). "
              "تأكد من الرقم قبل الحفظ.", weight=weight, max=max_weight)
        )


def validate_price(price: float | None, *, field_label: str = None) -> None:
    if price is None:
        return
    if field_label is None:
        field_label = _("السعر")
    if price < 0:
        raise ValueError(_("%(field)s ما يقدر يكون رقماً سالباً.", field=field_label))


MAX_MILK_LITERS_PER_SESSION = 15


def validate_milk_quantity(quantity_liters: float | None) -> None:
    """بند إصلاح (فحص "أكواد الحيوانات") — قيد الوزن (`validate_weight`)
    والسعر (`validate_price`) عندهما فحص منطقي قبل الحفظ، لكن قيد الحليب
    (`add_milk_record`) ما عنده أي فحص إطلاقاً — كمية سالبة أو صفرية أو
    خطأ كتابة واضح (فاصلة بمكان غلط، مثلاً 250 بدل 2.5) كانت تُحفظ بدون
    أي اعتراض، تلوّث تقارير إنتاج الحليب وتنبيهات فترة السحب. نفس نمط
    وفلسفة `validate_weight` بالضبط — حد أقصى واسع عمداً (15 لتر بالحلبة
    الواحدة، أعلى بكثير من أي إنتاج طبيعي فعلي لغنم/ماعز) يمنع خطأ كتابة
    واضح بدون رفض قيم نادرة لكن ممكنة."""
    if quantity_liters is None:
        return
    if quantity_liters <= 0:
        raise ValueError(_("كمية الحليب لازم تكون رقماً موجباً أكبر من صفر."))
    if quantity_liters > MAX_MILK_LITERS_PER_SESSION:
        raise ValueError(
            _("كمية %(qty)s لتر غير منطقية لحلبة واحدة — أعلى من الحد المتوقع (%(max)s لتر). "
              "تأكد من الرقم قبل الحفظ.", qty=quantity_liters, max=MAX_MILK_LITERS_PER_SESSION)
        )


def validate_not_future_date(value: date | None, *, field_label: str = None) -> None:
    """بند إصلاح (فحص عميق — تحليل شامل) — كانت تستخدم `date.today()`
    الخام (وقت سيرفر Render UTC) بدل `farm_today()`. هذي الدالة المشتركة
    تُستدعى من عدة شاشات إدخال حقيقية (المالية، سجل الحليب...)، وعكس
    بقية إصلاحات التوقيت السابقة (حافة نادرة قرب منتصف الليل)، هذا
    الخلل يتكرر **يومياً وبدون استثناء** بنافذة 3 ساعات ثابتة: آخر 3
    ساعات من كل يوم UTC (21:00-23:59) تقابل أول 3 ساعات من اليوم
    *التالي* بالسعودية (00:00-02:59) — يعني أي مستخدم سعودي يسجّل عملية
    بتاريخ "اليوم" الحقيقي خلال هذي النافذة كان يُرفَض بخطأ "التاريخ
    بالمستقبل" بالغلط، لأن UTC لسا يعتبره الغد."""
    if value is None:
        return
    if field_label is None:
        field_label = _("التاريخ")
    from app.extensions import farm_today
    if value > farm_today():
        raise ValueError(_("%(field)s ما يقدر يكون بالمستقبل.", field=field_label))


def weight_outlier_percent(new_weight: float, previous_weight: float | None) -> float | None:
    """يرجّع نسبة التغيّر المطلقة (%) عن آخر وزن مسجَّل، أو None لو ما
    فيه وزن سابق يُقارَن به — لا يمنع، بس يُستخدَم بالواجهة لعرض تحذير
    "رقم شاذ" يحتاج تأكيداً صريحاً قبل الحفظ."""
    if not previous_weight or previous_weight <= 0:
        return None
    return abs(new_weight - previous_weight) / previous_weight * 100


WEIGHT_OUTLIER_THRESHOLD_PERCENT = 40
