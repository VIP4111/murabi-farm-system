"""
تعدد المستودعات (بند إضافي 52، جزء 3) — قرارك الصريح: طبقة إضافية فوق
الإجمالي الحالي، مو استبدالاً له. `Feed.available_qty` / `Pharmacy.
available_qty` يبقيان المرجع الصحيح دائماً بلا أي تعديل — كل دالة
موجودة أصلاً تتعامل معهما (حركات العلف، خصم العلاج، تنبيهات النقص...)
تشتغل بلا أي تعديل عليها إطلاقاً (صفر تغيير على ~10 ملفات مُختبرة أصلاً).

المستودع الافتراضي (`is_default=True`) يمثّل "الرصيد العام غير
المُوزَّع" ويُحتسب بالطرح (الإجمالي ناقص كل المستودعات المسمّاة
الأخرى) بدل ما يُخزَّن كصف — فأي تحديث لـ available_qty بأي مكان
بالنظام ينعكس عليه تلقائياً بدون أي بوابة أو استدعاء إضافي. المستودعات
المسمّاة الأخرى تتغيّر فقط عبر `transfer_stock` الصريح (خصم من A +
إضافة B بعملية واحدة)، وهي بالتعريف لا تُغيّر الإجمالي — مجرد نقل مكان.
"""
from flask_babel import gettext as _
from app.extensions import db
from app.models import AuditLog, Feed, FeedWarehouseStock, Pharmacy, PharmacyWarehouseStock, Warehouse

_DEFAULT_NAMES = {"feed": "المستودع الرئيسي (علف)", "pharmacy": "صيدلية المزرعة الرئيسية"}
_MODELS = {
    "feed": (FeedWarehouseStock, "feed_id"),
    "pharmacy": (PharmacyWarehouseStock, "pharmacy_id"),
}


def _model_and_fk(kind: str):
    if kind not in _MODELS:
        raise ValueError(_('نوع مخزون غير معروف: "%(kind)s"', kind=kind))
    return _MODELS[kind]


def get_or_create_default_warehouse(kind: str) -> Warehouse:
    existing = Warehouse.query.filter_by(warehouse_type=kind, is_default=True).first()
    if existing:
        return existing
    warehouse = Warehouse(name=_DEFAULT_NAMES[kind], warehouse_type=kind, is_default=True)
    db.session.add(warehouse)
    db.session.commit()
    return warehouse


def _named_rows(item, kind: str):
    """كل صفوف المستودعات المسمّاة (غير الافتراضية) لهذا الصنف — مرتبطة
    فعلياً بمستودع، بغض النظر عن كميتها (حتى لو صفر)."""
    model, fk = _model_and_fk(kind)
    return (
        model.query.join(Warehouse, model.warehouse_id == Warehouse.id)
        .filter(getattr(model, fk) == item.id, Warehouse.is_default.is_(False))
        .all()
    )


def warehouse_breakdown(item, kind: str) -> list[dict]:
    """توزيع المخزون الحالي لصنف على كل المستودعات — المستودع الافتراضي
    محسوب كباقي (الإجمالي ناقص المستودعات المسمّاة)، والباقي مقروء
    مباشرة. `inconsistent=True` لو الإجمالي انخفض (باستهلاك عادي خارج
    هذي الطبقة) تحت المُوزَّع فعلياً على المستودعات المسمّاة — حالة
    نادرة، تُعرض كملاحظة بالواجهة بدل ما تُكسر الحساب."""
    default_wh = get_or_create_default_warehouse(kind)
    named_rows = [r for r in _named_rows(item, kind) if r.qty]
    named_total = sum(r.qty for r in named_rows)
    default_qty = (item.available_qty or 0) - named_total

    result = [{
        "warehouse": default_wh, "qty": max(0.0, default_qty), "is_default": True,
        "inconsistent": default_qty < 0,
    }]
    for row in named_rows:
        result.append({"warehouse": row.warehouse, "qty": row.qty, "is_default": False})
    return result


def _get_or_create_named_row(item, kind: str, warehouse: Warehouse):
    model, fk = _model_and_fk(kind)
    row = model.query.filter_by(**{fk: item.id, "warehouse_id": warehouse.id}).first()
    if row:
        return row
    row = model(**{fk: item.id, "warehouse_id": warehouse.id, "qty": 0})
    db.session.add(row)
    return row


def _item_for(kind: str, item_id: int):
    Model = Feed if kind == "feed" else Pharmacy
    item = Model.query.get(item_id)
    if not item:
        raise ValueError(_("الصنف غير موجود."))
    return item


def transfer_stock(*, kind: str, item_id: int, from_warehouse_id: int, to_warehouse_id: int,
                    qty: float, actor_user_id: int) -> list[dict]:
    """تحويل صريح بين مستودعين — خصم من المصدر + إضافة للوجهة بعملية
    واحدة، بدون أي تأثير على `available_qty` الإجمالي (مجرد نقل مكان
    داخل نفس المزرعة). لو أحد الطرفين المستودع الافتراضي، ما فيه صف
    يُخزَّن له (رصيده محسوب بالطرح تلقائياً — تحويل منه أو له بس يغيّر
    الطرف الآخر المسمّى)."""
    if qty is None or qty <= 0:
        raise ValueError(_("الكمية لازم تكون أكبر من صفر."))
    if from_warehouse_id == to_warehouse_id:
        raise ValueError(_("لازم يكون المصدر والوجهة مستودعين مختلفين."))

    item = _item_for(kind, item_id)
    default_wh = get_or_create_default_warehouse(kind)
    breakdown = {e["warehouse"].id: e for e in warehouse_breakdown(item, kind)}

    if from_warehouse_id not in breakdown:
        raise ValueError(_("مستودع المصدر غير معروف لهذا الصنف."))
    available = breakdown[from_warehouse_id]["qty"]
    if qty > available:
        raise ValueError(_(
            'الكمية المطلوب تحويلها (%(qty)s) أكبر من المتوفر فعلياً بمستودع '
            '"%(wh)s" (%(available)s).',
            qty=qty, wh=breakdown[from_warehouse_id]["warehouse"].name, available=available,
        ))

    if from_warehouse_id != default_wh.id:
        from_row = _get_or_create_named_row(item, kind, breakdown[from_warehouse_id]["warehouse"])
        from_row.qty = (from_row.qty or 0) - qty
        db.session.add(from_row)

    if to_warehouse_id != default_wh.id:
        to_warehouse = Warehouse.query.get(to_warehouse_id)
        if not to_warehouse:
            raise ValueError(_("مستودع الوجهة غير موجود."))
        to_row = _get_or_create_named_row(item, kind, to_warehouse)
        to_row.qty = (to_row.qty or 0) + qty
        db.session.add(to_row)

    db.session.add(AuditLog(
        actor_user_id=actor_user_id, action="warehouse.transfer",
        entity_type=kind, entity_id=item.id,
        details=f'{qty} من مستودع #{from_warehouse_id} إلى #{to_warehouse_id}',
    ))
    db.session.commit()
    return warehouse_breakdown(item, kind)
