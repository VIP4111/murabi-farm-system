"""بند إضافي 205 — طلبك: اعتماد شعار "مراح بو علي" كأيقونة رسمية موحّدة
(favicon، apple-touch-icon، PWA manifest، وشعار الـnavbar/القائمة
الجانبية/شاشة الدخول) بدل الإيموجي 🐑 المؤقت."""
import json
import os

from app.extensions import db
from app.models import Role, User


ASSET_PATHS = [
    "app/static/favicon.ico",
    "app/static/icons/icon-16.png",
    "app/static/icons/icon-32.png",
    "app/static/icons/icon-96.png",
    "app/static/icons/apple-touch-icon.png",
    "app/static/icons/icon-192.png",
    "app/static/icons/icon-512.png",
]


def test_all_icon_assets_exist_on_disk():
    for path in ASSET_PATHS:
        assert os.path.isfile(path), f"ملف الأيقونة مفقود: {path}"


def test_manifest_points_to_real_icon_files():
    with open("app/static/manifest.webmanifest") as f:
        manifest = json.load(f)
    srcs = {icon["src"] for icon in manifest["icons"]}
    assert "/static/icons/icon-192.png" in srcs
    assert "/static/icons/icon-512.png" in srcs


def _make_owner(phone="0599999180"):
    role = Role.query.filter_by(name="owner").first()
    user = User(name="مالك اختبار الهوية البصرية", phone=phone, role_id=role.id, language="ar")
    user.set_password("test1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_login_page_links_favicon_and_apple_touch_icon(app, client):
    resp = client.get("/login")
    body = resp.data.decode()
    assert 'rel="icon" type="image/x-icon" href="/static/favicon.ico"' in body
    assert 'rel="apple-touch-icon"' in body
    assert 'icons/apple-touch-icon.png' in body
    assert 'rel="manifest"' in body


def test_login_page_navbar_uses_logo_image_not_emoji(app, client):
    resp = client.get("/login")
    body = resp.data.decode()
    assert '<div class="logo">🐑</div>' not in body
    assert 'class="logo"><img src="/static/icons/icon-96.png"' in body


def test_authenticated_home_sidebar_shows_logo(app, client):
    owner = _make_owner()
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    resp = client.get("/")
    body = resp.data.decode()
    assert body.count('icons/icon-96.png') >= 2  # navbar + side-menu-head
