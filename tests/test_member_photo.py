"""بند إضافي (2026-08-31) — طلبك المباشر: صورة شخصية اختيارية لكل
عضو فريق. نفس آلية رفع صورة دليل البلاغ بالضبط (Cloudinary لو مضبوط،
وإلا محلي)، فاضي = بدون صورة (أيقونة افتراضية بالواجهة)، صفر كسر لأي
حساب موجود مسبقاً بدون صورة."""
import io

from app.extensions import db
from app.models import User


def _image_bytes():
    return io.BytesIO(b"\xff\xd8\xff" + b"0" * 100), "photo.jpg"


def test_members_new_saves_uploaded_photo(app, logged_in_client):
    stream, filename = _image_bytes()
    resp = logged_in_client.post("/team/members/new", data={
        "name": "عضو بصورة", "phone": "0599999310", "password": "pass1234",
        "role_id": "1", "language": "ar", "photo": (stream, filename),
    }, content_type="multipart/form-data", follow_redirects=True)
    assert resp.status_code == 200
    user = User.query.filter_by(phone="0599999310").first()
    assert user is not None
    assert user.photo_url is not None
    assert user.photo_url.startswith("/uploads/team_photos/")


def test_members_new_without_photo_leaves_photo_url_none(app, logged_in_client):
    resp = logged_in_client.post("/team/members/new", data={
        "name": "عضو بلا صورة", "phone": "0599999311", "password": "pass1234",
        "role_id": "1", "language": "ar",
    }, follow_redirects=True)
    assert resp.status_code == 200
    user = User.query.filter_by(phone="0599999311").first()
    assert user is not None
    assert user.photo_url is None


def test_members_edit_replaces_existing_photo(app, logged_in_client, worker):
    worker.photo_url = "/uploads/team_photos/old.jpg"
    db.session.commit()

    stream, filename = _image_bytes()
    resp = logged_in_client.post(f"/team/members/{worker.id}/edit", data={
        "name": worker.name, "phone": worker.phone, "role_id": str(worker.role_id),
        "language": "ar", "photo": (stream, filename),
    }, content_type="multipart/form-data", follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(worker)
    assert worker.photo_url is not None
    assert worker.photo_url != "/uploads/team_photos/old.jpg"


def test_members_edit_remove_photo_checkbox_clears_it(app, logged_in_client, worker):
    worker.photo_url = "/uploads/team_photos/old.jpg"
    db.session.commit()

    resp = logged_in_client.post(f"/team/members/{worker.id}/edit", data={
        "name": worker.name, "phone": worker.phone, "role_id": str(worker.role_id),
        "language": "ar", "remove_photo": "1",
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(worker)
    assert worker.photo_url is None
