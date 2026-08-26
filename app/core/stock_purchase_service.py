"""شراء موحّد للعلف/المعدات/الأدوية (بند إضافي 203، وُسِّعت للصيدلية
ببند 259) — طلبك: زر "شراء" واحد داخل شاشة "مكوّنات العلف"/"المعدات"
يزيد المخزون **ويسجّل العملية المالية** بنفس الوقت، بدل ما تدخل من
"حركة المخزون" و"المالية ← عملية جديدة" كل مرة لحالها. الدالتين هنا
نقطة دخول واحدة تربط `feed_service`/`equipment_service.record_movement`
(وارد) — أو `PharmacyBatch` للصيدلية — بإنشاء `Finance` (شراء)، بدون
تكرار منطق الخصم/الجمع الموجود أصلاً بكل خدمة.

**بند 259**: لُقِط إن "شراء دواء" (`health.pharmacy_purchase`، بند 96)
كان يسجّل دفعة (`PharmacyBatch`) ويزيد المخزون، بس **بدون أي عملية
مالية** — المبلغ المدفوع كان يختفي تماماً من كل تقارير المالية
(الإجمالي، تكلفة الرأس الشهرية، تشخيص الخسارة...). وُصِّلت هنا بنفس
النمط الموحّد المستخدم للعلف/المعدات، بفرق واحد: `unit_price` هنا
اختياري (كان اختيارياً بالفورم الأصلي) — لو ما انكتب، يُسجَّل الشراء
بالمخزون فقط بدون Finance (ما نخترع سعر)، مع تحذير واضح للمستخدم."""
from app.extensions import db
from app.models import Feed, Equipment, Finance, PharmacyBatch
from app.finance.finance_service import save_invoice_file

KIND_LABELS = {"feed": "أعلاف", "equipment": "معدات", "pharmacy": "أدوية"}


def record_purchase(*, kind: str, item, quantity: float, unit_price: float | None, purchase_date,
                     invoice_file=None, note=None, created_by_id=None, expiry_date=None):
    """`kind` = "feed" أو "equipment" أو "pharmacy". يسجّل حركة "وارد"
    بمستودع الصنف (ترفع `available_qty` فوراً) — للعلف/المعدات عبر
    `record_movement`، للصيدلية عبر دفعة `PharmacyBatch` جديدة (نفس
    آلية بند 96، `item.add_stock`) — وعملية مالية "شراء" بنفس المبلغ
    (الكمية × سعر الوحدة) لو `unit_price` معطى، مربوطة بفاتورة المورّد
    لو انرفعت. `unit_price=None` يسجّل حركة المخزون بس، بدون Finance
    (ما نخترع سعر غير موجود) — المستدعي مسؤول يحذّر المستخدم بهالحالة."""
    fin = None
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
    elif kind == "pharmacy":
        movement = PharmacyBatch(
            pharmacy_id=item.id, purchase_date=purchase_date, quantity=quantity,
            remaining_qty=quantity, expiry_date=expiry_date, unit_price=unit_price,
            notes=note, created_by_id=created_by_id,
        )
        item.add_stock(quantity)
        db.session.add(item)
        db.session.add(movement)
    else:
        raise ValueError(f'kind غير معروف: {kind}')

    if unit_price is not None:
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
