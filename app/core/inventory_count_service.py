"""جرد المستودعات (بند إضافي 208) — طلبك بالنص: "عندك شعير 40 كيلو،
أجي أحسب [بالميزان] زاد عندي 5 كيلو... نقول هذا زايد يدخل ضمن
المخزون. لو نقص عن 40... نقول الهالك 10 كيلو تحسبها خسارة على
المشروع... تقول قيمة الهالك بسعر الكيس الأصلي، تضيف الخسارة على سعر
الخراف [موزَّعة على كل الرؤوس]." الدالة هنا نقطة دخول واحدة تغطي
العلف/الدواء/المعدات الثلاثة (نفس نمط `stock_purchase_service.kind`)."""
from datetime import date

from app.extensions import db
from app.models import Feed, Pharmacy, Equipment, Finance, InventoryCount

KIND_MODELS = {"feed": Feed, "pharmacy": Pharmacy, "equipment": Equipment}
KIND_LABELS_AR = {"feed": "أعلاف", "pharmacy": "دواء", "equipment": "معدات"}


def record_count(*, kind: str, item, actual_qty: float, count_date=None, note=None, created_by_id=None):
    """يصحّح رصيد الصنف للكمية الفعلية المجرودة. النقص يُسجَّل هالك —
    مصروف غير مباشر (`is_indirect=True`) بقيمة الفرق × سعر الوحدة،
    يُوزَّع تلقائياً على الرؤوس النشطة بنفس تقارير التكلفة الموجودة.
    الزيادة تصحيح مخزون بس، صفر أثر مالي (اكتشاف كمية موجودة فعلاً،
    مو "ربح")."""
    if kind not in KIND_MODELS:
        raise ValueError(f'kind غير معروف: {kind}')

    count_date = count_date or date.today()
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
