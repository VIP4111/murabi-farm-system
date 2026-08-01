"""بند إضافي 77 — تجهيز قابلية النقل لـPostgreSQL + مجلد رفع ملفات
قابل للتوجيه (بدل الاعتماد الدائم على static/ داخل حاوية Render
المؤقتة). لا يغيّر أي سلوك افتراضي — SQLite ومسار static/uploads
يبقيان يشتغلان بالضبط زي قبل بدون أي إعداد إضافي."""
import io
from app.config import _normalize_database_url


def test_normalize_database_url_converts_legacy_postgres_scheme():
    assert (
        _normalize_database_url("postgres://user:pass@host/db")
        == "postgresql://user:pass@host/db"
    )


def test_normalize_database_url_leaves_other_schemes_untouched():
    assert _normalize_database_url("sqlite:///farm_system.db") == "sqlite:///farm_system.db"
    assert (
        _normalize_database_url("postgresql://user:pass@host/db")
        == "postgresql://user:pass@host/db"
    )


def test_upload_dir_defaults_under_static_folder_when_unset(app):
    assert app.config["UPLOAD_DIR"].endswith("static/uploads") or app.config["UPLOAD_DIR"].endswith("static\\uploads")


def test_save_evidence_image_returns_new_uploads_url_not_static(app):
    from app.team.report_service import save_evidence_image
    fake = _FakeFileStorage("test.jpg", b"\xff\xd8\xff" + b"0" * 100)
    with app.app_context():
        url = save_evidence_image(fake)
    assert url is not None
    assert url.startswith("/uploads/images/")
    assert "/static/" not in url


def test_uploaded_file_route_serves_saved_image(app, client, logged_in_client):
    from app.team.report_service import save_evidence_image
    fake = _FakeFileStorage("test2.png", b"\x89PNG" + b"0" * 100)
    with app.app_context():
        url = save_evidence_image(fake)
    resp = logged_in_client.get(url)
    assert resp.status_code == 200


class _FakeFileStorage:
    def __init__(self, filename, data):
        self.filename = filename
        self.stream = io.BytesIO(data)

    def save(self, path):
        with open(path, "wb") as f:
            f.write(self.stream.getvalue())
