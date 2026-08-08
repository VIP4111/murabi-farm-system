"""بند إضافي 151 — طلبك: قرص Render المجاني يُمسح مع كل نشر، فأي صورة/
صوت مرفوع كان يضيع. حل مجاني (Cloudinary عبر REST مباشرة، بدون SDK
جديد) مع تراجع آمن للتخزين المحلي لو المفاتيح غير مضبوطة."""
import io

from werkzeug.datastructures import FileStorage

from app.core import cloud_storage_service as svc


def _file(name="test.jpg", content=b"x" * 100):
    return FileStorage(stream=io.BytesIO(content), filename=name)


def test_no_file_returns_none(app):
    assert svc.save_upload(None, subfolder="images", allowed_extensions={"jpg"}, max_bytes=1000) is None


def test_rejected_extension_returns_none(app):
    f = _file(name="test.exe")
    assert svc.save_upload(f, subfolder="images", allowed_extensions={"jpg"}, max_bytes=1000) is None


def test_oversized_file_returns_none(app):
    f = _file(content=b"x" * 2000)
    assert svc.save_upload(f, subfolder="images", allowed_extensions={"jpg"}, max_bytes=1000) is None


def test_falls_back_to_local_storage_without_cloudinary_env(app, monkeypatch):
    monkeypatch.delenv("CLOUDINARY_CLOUD_NAME", raising=False)
    monkeypatch.delenv("CLOUDINARY_API_KEY", raising=False)
    monkeypatch.delenv("CLOUDINARY_API_SECRET", raising=False)
    f = _file()
    url = svc.save_upload(f, subfolder="images", allowed_extensions={"jpg"}, max_bytes=1000)
    assert url is not None
    assert url.startswith("/uploads/images/")


def test_uses_cloudinary_when_configured(app, monkeypatch):
    monkeypatch.setenv("CLOUDINARY_CLOUD_NAME", "demo")
    monkeypatch.setenv("CLOUDINARY_API_KEY", "key")
    monkeypatch.setenv("CLOUDINARY_API_SECRET", "secret")

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"secure_url": "https://res.cloudinary.com/demo/image/upload/abc.jpg"}

    def fake_post(url, data=None, files=None, timeout=None):
        assert "demo" in url
        return FakeResponse()

    monkeypatch.setattr(svc.requests, "post", fake_post)

    f = _file()
    url = svc.save_upload(f, subfolder="images", allowed_extensions={"jpg"}, max_bytes=1000)
    assert url == "https://res.cloudinary.com/demo/image/upload/abc.jpg"


def test_falls_back_to_local_when_cloudinary_upload_fails(app, monkeypatch):
    monkeypatch.setenv("CLOUDINARY_CLOUD_NAME", "demo")
    monkeypatch.setenv("CLOUDINARY_API_KEY", "key")
    monkeypatch.setenv("CLOUDINARY_API_SECRET", "secret")

    import requests as requests_module

    def fake_post(url, data=None, files=None, timeout=None):
        raise requests_module.RequestException("network down")

    monkeypatch.setattr(svc.requests, "post", fake_post)

    f = _file()
    url = svc.save_upload(f, subfolder="images", allowed_extensions={"jpg"}, max_bytes=1000)
    assert url is not None
    assert url.startswith("/uploads/images/")
