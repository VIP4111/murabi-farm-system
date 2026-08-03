"""مستودع المعدات (بند إضافي 108) — نفس بنية `feed_service.record_movement`
بالضبط، بدون منطق نحاس/نبأت (ما ينطبق على معدات)."""
from datetime import date, timedelta

from app.extensions import db
from app.models import Equipment, EquipmentMovement


def record_movement(*, item: Equipment, movement_type: str, quantity: float, barn_id=None,
                     note=None, created_by_id=None) -> EquipmentMovement:
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
    )
    db.session.add(mv)
    db.session.add(item)
    db.session.commit()
    return mv


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
