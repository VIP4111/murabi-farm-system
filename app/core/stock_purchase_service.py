"""شراء موحّد للعلف/المعدات (بند إضافي 203) — طلبك: زر "شراء" واحد داخل
شاشة "مكوّنات العلف"/"المعدات" يزيد المخزون **ويسجّل العملية المالية**
بنفس الوقت، بدل ما تدخل من "حركة المخزون" و"المالية ← عملية جديدة"
كل مرة لحالها. الدالتين هنا نقطة دخول واحدة تربط `feed_service`/
`equipment_service.record_movement` (وارد) بإنشاء `Finance` (شراء)،
بدون تكرار منطق الخصم/الجمع الموجود أصلاً بكل خدمة."""
from app.extensions import db
from app.models import Feed, Equipment, Finance
from app.finance.finance_service import save_invoice_file

KIND_LABELS = {"feed": "أعلاف", "equipment": "معدات"}


def record_purchase(*, kind: str, item, quantity: float, unit_price: float, purchase_date,
                     invoice_file=None, note=None, created_by_id=None):
    """`kind` = "feed" أو "equipment". يسجّل حركة "وارد" بمستودع الصنف
    (ترفع `available_qty` فوراً) وعملية مالية "شراء" بنفس المبلغ
    (الكمية × سعر الوحدة) مربوطة بفاتورة المورّد لو انرفعت — عملية
    واحدة بالنظر للمستخدم، سجلّين مترابطين فعلياً (نفس أساس أي تقرير
    تكلفة شهرية يعتمد على `Finance`)."""
    if kind == "feed":
        from app.feed import feed_service
        movement = feed_service.record_movement(
            feed=item, movement_type="in", quantity=quantity, note=note, created_by_id=created_by_id,
        )
    elif kind == "equipment":
        from app.equipment import equipment_service
        movement = equipment_service.record_movement(
            item=item, movement_type="in", quantity=quantity, note=note, created_by_id=created_by_id,
        )
    else:
        raise ValueError(f'kind غير معروف: {kind}')

    # تحديث سعر الوحدة المرجعي بآخر سعر شراء فعلي (بدل ما يضل قديماً
    # يدوياً) — نفس القيمة اللي يعتمد عليها تقرير "طلب الشراء" (بند 156)
    # باختيار الأرخص بين الأصناف البديلة.
    item.unit_price = unit_price
    db.session.add(item)

    fin = Finance(
        date=purchase_date, operation_type="purchase", category=KIND_LABELS[kind],
        item=item.name, description=note,
        amount=round(quantity * unit_price, 2),
        invoice_file_url=save_invoice_file(invoice_file) if invoice_file else None,
    )
    db.session.add(fin)
    db.session.commit()
    return movement, fin
