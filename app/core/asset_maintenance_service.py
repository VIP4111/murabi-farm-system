"""مهام صيانة الأصول المستحقة (بند إضافي 186) — نفس فلسفة
`scheduled_care_service.generate_vaccination_due_tasks` بالضبط: فحص حي
عند فتح شاشة التنبيهات، idempotent عبر `source_type`/`source_id`،
صفر Cron جديد."""
import zlib
from datetime import datetime, timedelta

from app.models import Asset, Task
from app.team import task_service

MAINTENANCE_SOURCE_TYPE = "AssetMaintenanceDue"


def _source_id(asset_id: int) -> int:
    return zlib.crc32(f"asset_maintenance:{asset_id}".encode()) & 0x7FFFFFFF


def generate_maintenance_due_tasks(*, now: datetime | None = None) -> list:
    today = (now or datetime.now()).date()
    created = []

    assets = Asset.query.filter(
        Asset.status == "active", Asset.maintenance_interval_days.isnot(None),
    ).all()
    for asset in assets:
        reference = asset.last_maintenance_date or asset.created_at.date()
        due_date = reference + timedelta(days=asset.maintenance_interval_days)
        if due_date > today:
            continue
        source_id = _source_id(asset.id)
        existing = Task.query.filter(
            Task.source_type == MAINTENANCE_SOURCE_TYPE, Task.source_id == source_id,
            Task.status.in_(task_service.OPEN_TASK_STATUSES),
        ).first()
        if existing:
            continue
        overdue_days = (today - due_date).days
        task = task_service.create_suggested_task(
            title=f"🔧 صيانة مستحقة — {asset.name}",
            task_type="asset_maintenance", barn_id=asset.barn_id,
            due_date=today, source_type=MAINTENANCE_SOURCE_TYPE, source_id=source_id,
            notes=f"آخر صيانة مسجَّلة كانت {reference} — استحقت التجديد منذ {overdue_days} يوم.",
        )
        created.append(task)
    return created
