"""جرد المستودعات (بند إضافي 208) — طلبك بالنص: "عندك شعير 40 كيلو،
أجي أحسب [بالميزان] زاد عندي 5 كيلو... نقول هذا زايد يدخل ضمن
المخزون. لو نقص عن 40... نقول الهالك 10 كيلو تحسبها خسارة على
المشروع... تقول قيمة الهالك بسعر الكيس الأصلي، تضيف الخسارة على سعر
الخراف [موزَّعة على كل الرؤوس]." الدالة هنا نقطة دخول واحدة تغطي
العلف/الدواء/المعدات الثلاثة (نفس نمط `stock_purchase_service.kind`)."""
from flask_babel import gettext as _
from flask_babel import lazy_gettext as _l

from app.extensions import db
from app.models import Feed, Pharmacy, Equipment, Finance, InventoryCount

KIND_MODELS = {"feed": Feed, "pharmacy": Pharmacy, "equipment": Equipment}
# بند إصلاح (فحص عميق — طلبك: "افحص جميع النوافذ بعمق") — نفس فجوة
# `medicine_class` بالضبط: نص عربي خام بدون `_l()` بشاشة جرد المستودعات.
KIND_LABELS_AR = {"feed": _l("أعلاف"), "pharmacy": _l("دواء"), "equipment": _l("معدات")}


def record_count(*, kind: str, item, actual_qty: float, count_date=None, note=None, created_by_id=None):
    """يصحّح رصيد الصنف للكمية الفعلية المجرودة. النقص يُسجَّل هالك —
    مصروف غير مباشر (`is_indirect=True`) بقيمة الفرق × سعر الوحدة،
    يُوزَّع تلقائياً على الرؤوس النشطة بنفس تقارير التكلفة الموجودة.
    الزيادة تصحيح مخزون بس، صفر أثر مالي (اكتشاف كمية موجودة فعلاً،
    مو "ربح")."""
    if kind not in KIND_MODELS:
        raise ValueError(f'kind غير معروف: {kind}')
    # بند إصلاح (فحص عميق — قسم المستودعات) — `actual_qty` ما كان عليها
    # أي تحقق — قيمة سالبة (خطأ كتابة بالميزان) كانت تُخزَّن مباشرة
    # كرصيد مخزون سالب (`item.available_qty`)، وتحسب "هالك" مضخَّماً
    # بالغلط (الفرق كامل بين الرصيد المتوقع وسالب الكمية المُدخلة) —
    # يُرحَّل كمصروف حقيقي بسجل المالية بقيمة فاسدة.
    if actual_qty is None or actual_qty < 0:
        raise ValueError(_("الكمية الفعلية المجرودة لازم تكون رقماً موجباً (أو صفر)."))

    # بند إصلاح (فحص شامل سطر بسطر — ميزة المستودعات) — هذي الدالة
    # تفترض الجرد يغطي كل رصيد الصنف دفعة وحدة (available_qty كاملاً)،
    # بدون أي وعي بالمستودعات المسمّاة (`warehouse_breakdown`). لو صنف
    # عنده كمية موزَّعة فعلياً على مستودع مسمّى، وجاء جرد بكمية أقل من
    # هذا الموزَّع، كان يُحفَظ بصمت ويخلي المستودع الافتراضي المحسوب
    # سالباً (يُقصّ لصفر) — يعني مجموع البطاقة المعروضة يصير أكبر من
    # الرصيد الفعلي الجديد، مخالفة صريحة للقاعدة الموثَّقة "مجموع
    # المستودعات = الرصيد الإجمالي دائماً". صار يُرفض صراحة بدل ما يُحفظ
    # فاسداً، ويطلب مراجعة توزيع المستودعات أولاً.
    if kind in ("feed", "pharmacy"):
        from app.core import warehouse_service
        named_total = sum(
            row["qty"] for row in warehouse_service.warehouse_breakdown(item, kind) if not row["is_default"]
        )
        if named_total > 0 and actual_qty < named_total:
            raise ValueError(_(
                "الكمية المجرودة (%(actual)s) أقل من المجموع الموزَّع فعلياً على "
                "مستودعات مسمّاة لهذا الصنف (%(named)s) — راجع توزيع المستودعات "
                "قبل تسجيل الجرد.", actual=actual_qty, named=named_total,
            ))

    from app.extensions import farm_today
    count_date = count_date or farm_today()
    expected_qty = item.available_qty or 0
    diff_qty = actual_qty - expected_qty

    fin = None
    diff_value = None
    if diff_qty < 0:
        loss_qty = abs(diff_qty)
        diff_value = round(loss_qty * (item.unit_price or 0), 2)
        fin = Finance(
            date=count_date, operation_type="expense", category="هالك",
            item=item.name, is_indirect=True, amount=diff_value,
            description=(
                f'جرد {count_date}: رصيد النظام {expected_qty} والفعلي بالميزان {actual_qty} '
                f'— نقص {loss_qty} يُحتسب هالك.'
            ),
        )
        db.session.add(fin)
        db.session.flush()

    item.available_qty = actual_qty
    db.session.add(item)

    rec = InventoryCount(
        kind=kind, item_id=item.id, item_name=item.name, count_date=count_date,
        expected_qty=expected_qty, actual_qty=actual_qty, diff_qty=diff_qty,
        diff_value=diff_value, finance_id=fin.id if fin else None,
        note=note, created_by_id=created_by_id,
    )
    db.session.add(rec)
    db.session.commit()
    return rec
