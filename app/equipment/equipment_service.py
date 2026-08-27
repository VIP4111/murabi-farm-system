"""مستودع المعدات (بند إضافي 108) — نفس بنية `feed_service.record_movement`
بالضبط، بدون منطق نحاس/نبأت (ما ينطبق على معدات)."""
from datetime import date, datetime, timedelta, timezone

from app.extensions import db
from app.models import Equipment, EquipmentMovement
from app.core.cloud_storage_service import save_upload

ALLOWED_PHOTO_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "heic", "heif"}
MAX_PHOTO_BYTES = 8 * 1024 * 1024


def _now():
    return datetime.now(timezone.utc)


def save_equipment_photo(file_storage) -> str | None:
    """صورة صنف معدات (بند إضافي 199) — نفس آلية `save_evidence_image`
    بالضبط (سحابياً لو مضبوط Cloudinary، وإلا محلياً)."""
    return save_upload(file_storage, subfolder="images",
                        allowed_extensions=ALLOWED_PHOTO_EXTENSIONS, max_bytes=MAX_PHOTO_BYTES)


def record_maintenance_cost(*, asset, cost: float | None, date_) -> int | None:
    """يربط تكلفة صيانة أصل بعملية مالية حقيقية (بند إضافي 263) —
    قبل هذا البند، `AssetMaintenanceLog.cost` كان يُخزَّن بس، بدون أي
    أثر بسجل "المالية" العام. مصروف حقيقي جديد (مو استهلاك مخزون
    مدفوع من قبل)، فما فيه احتمال احتساب مزدوج — أي تكلفة > 0 تُنشئ
    عملية مالية مباشرة."""
    if not cost or cost <= 0:
        return None
    from app.models import Finance
    fin = Finance(
        date=date_, operation_type="expense", category="صيانة معدات",
        item=asset.name, amount=cost,
    )
    db.session.add(fin)
    db.session.flush()
    return fin.id


def record_utility_cost(*, utility_type: str, cost: float | None, date_) -> int | None:
    """يربط فاتورة كهرباء/ماء بعملية مالية حقيقية (بند إضافي 263) —
    نفس مبدأ `record_maintenance_cost` أعلاه."""
    if not cost or cost <= 0:
        return None
    from app.models import Finance
    label = "كهرباء" if utility_type == "electricity" else "ماء"
    fin = Finance(
        date=date_, operation_type="expense", category=f"فاتورة {label}",
        item=label, amount=cost,
    )
    db.session.add(fin)
    db.session.flush()
    return fin.id


def my_borrow(item, user_id):
    """آخر استعارة قائمة لهذا المستخدم لهذي القطعة (بند إضافي 199) —
    تُستخدم بشاشة العامل المبسّطة لتحديد لو زر "أخذ" أو "استرجاع"."""
    return (EquipmentMovement.query
            .filter_by(equipment_id=item.id, borrowed_by_id=user_id, returned_at=None)
            .order_by(EquipmentMovement.created_at.desc()).first())


def record_movement(*, item: Equipment, movement_type: str, quantity: float, barn_id=None,
                     note=None, created_by_id=None, borrowed_by_id=None) -> EquipmentMovement:
    """`borrowed_by_id` (بند إضافي 110) — يُعبَّى بس لو الصادر استعارة
    (أداة ترجع)، مو صرف نهائي. القطعة تُخصَم من الرصيد فوراً وقت
    الاستعارة (نفس أي صادر عادي) — ترجع للرصيد لما تُسجَّل `return_item`."""
    before = item.available_qty or 0
    if movement_type == "in":
        item.add_stock(quantity)
    else:
        item.deduct_stock(quantity)
    after = item.available_qty or 0

    mv = EquipmentMovement(
        equipment_id=item.id, movement_type=movement_type, quantity=quantity,
        before_qty=before, after_qty=after, barn_id=barn_id,
        note=note, created_by_id=created_by_id,
        borrowed_by_id=borrowed_by_id if movement_type == "out" else None,
    )
    db.session.add(mv)
    db.session.add(item)
    db.session.commit()
    return mv


def return_item(movement: EquipmentMovement) -> EquipmentMovement:
    """تسجيل استرجاع قطعة مستعارة (بند إضافي 110) — يرجّع الكمية
    للرصيد ويختم `returned_at` بوقت السيرفر. يرفض لو الحركة مو استعارة
    أصلاً أو رجعت من قبل — عشان ما ينضاف رصيد مرتين بالغلط."""
    if not movement.borrowed_by_id:
        raise ValueError("هذي الحركة مو استعارة أصلاً.")
    if movement.returned_at:
        raise ValueError("هذي القطعة مسجَّلة راجعة من قبل.")
    movement.returned_at = _now()
    movement.equipment.add_stock(movement.quantity)
    db.session.add(movement)
    db.session.add(movement.equipment)
    db.session.commit()
    return movement


def outstanding_borrows(item):
    """قطع مستعارة لسا ما رجعت (بند إضافي 110) — تُستخدم بشاشة والدك
    المبسّطة عشان يشوف مين مستلم شنو بدون ما يفتح شاشة الحركات الكاملة."""
    return (EquipmentMovement.query
            .filter_by(equipment_id=item.id, returned_at=None)
            .filter(EquipmentMovement.borrowed_by_id.isnot(None))
            .order_by(EquipmentMovement.created_at.desc()).all())


def consumption_stats(item, *, day_lookback: int = 1, month_lookback: int = 30) -> dict:
    """استهلاك آخر يوم وآخر 30 يوم — يُستخدم بشاشة "المستودع" المبسّطة
    (بند 108) لعرض نفس المقياس لأي صنف (علف/دواء/معدات) بدون تكرار
    منطق حساب لكل نوع لحاله."""
    def _consumed_since(days, model, id_field, id_value):
        since = date.today() - timedelta(days=days)
        return (db.session.query(db.func.coalesce(db.func.sum(model.quantity), 0))
                .filter(getattr(model, id_field) == id_value, model.movement_type == "out",
                        model.created_at >= since)
                .scalar()) or 0

    consumed_day = _consumed_since(day_lookback, EquipmentMovement, "equipment_id", item.id)
    consumed_month = _consumed_since(month_lookback, EquipmentMovement, "equipment_id", item.id)
    return {"consumed_day": consumed_day, "consumed_month": consumed_month}
