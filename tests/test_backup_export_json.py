"""بند إضافي (2026-09-01) — حادثة حقيقية: قاعدة PostgreSQL المجانية على
Render انتهت صلاحيتها تلقائياً (سياسة 90 يوم) وانقطع الوصول لكل
البيانات، وما كان فيه أي نسخة احتياطية فعلية لأن `backup_service` القديم
كان يشتغل على SQLite بس (`is_backup_supported()` ترجع False على
PostgreSQL). `export_all_tables_json()` الجديدة تشتغل بأي قاعدة بيانات
وتُرسَل مباشرة للتنزيل، بدون تخزين بالسيرفر."""
import json
from app.core import backup_service
from app.extensions import db
from tests.factories import make_animal, make_barn


def test_export_all_tables_json_includes_real_data(app, logged_in_client, owner):
    make_barn(barn_no="BK-EXPORT")
    make_animal(animal_no="EXPORT-01")

    buf = backup_service.export_all_tables_json()
    data = json.loads(buf.read().decode("utf-8"))

    assert "tables" in data
    assert "exported_at" in data
    assert "barns" in data["tables"]
    assert "animals" in data["tables"]
    assert any(row["barn_no"] == "BK-EXPORT" for row in data["tables"]["barns"])
    assert any(row["animal_no"] == "EXPORT-01" for row in data["tables"]["animals"])


def test_export_all_tables_json_works_regardless_of_is_backup_supported(app, owner):
    """الفحص الحاسم — التصدير الجديد يشتغل حتى لو is_backup_supported()
    (القديمة، الخاصة بـSQLite) ترجع False، لأنه لا يعتمد عليها إطلاقاً."""
    buf = backup_service.export_all_tables_json()
    data = json.loads(buf.read().decode("utf-8"))
    assert "users" in data["tables"]
    assert len(data["tables"]["users"]) >= 1  # المالك على الأقل


def test_export_all_tables_json_serializes_dates_safely(app, owner):
    from datetime import date
    from tests.factories import make_animal

    animal = make_animal(animal_no="EXPORT-DATE")
    animal.birth_date = date(2026, 1, 15)
    db.session.commit()

    buf = backup_service.export_all_tables_json()
    data = json.loads(buf.read().decode("utf-8"))
    row = next(r for r in data["tables"]["animals"] if r["animal_no"] == "EXPORT-DATE")
    assert row["birth_date"] == "2026-01-15"


def test_backup_export_now_route_returns_downloadable_json(app, logged_in_client, owner):
    # SEC-01: المسار صار POST (راجع tests/test_sec01_sw_cache_isolation.py)
    resp = logged_in_client.post("/settings/backup/export-now")
    assert resp.status_code == 200
    assert resp.mimetype == "application/json"
    assert "attachment" in resp.headers.get("Content-Disposition", "")
    data = json.loads(resp.data.decode("utf-8"))
    assert "tables" in data


def test_backup_export_now_requires_settings_manage_permission(app, client, worker):
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.post("/settings/backup/export-now")
    assert resp.status_code == 403


def test_backup_export_now_creates_audit_log_entry(app, logged_in_client, owner):
    from app.models import AuditLog

    logged_in_client.post("/settings/backup/export-now")
    entry = AuditLog.query.filter_by(action="backup.export_json").order_by(AuditLog.id.desc()).first()
    assert entry is not None
    assert entry.actor_user_id == owner.id


def test_settings_backup_page_shows_universal_download_button(app, logged_in_client):
    resp = logged_in_client.get("/settings/backup")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert "/settings/backup/export-now" in body
    assert "تنزيل نسخة احتياطية كاملة الآن" in body
