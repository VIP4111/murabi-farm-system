"""بند إضافي 93 (التحليل الثالث) — قبل هذا البند ما كان فيه أي رمز CSRF
بأي فورم بالمشروع. باقي اختبارات المشروع تعطّل CSRF عمداً
(WTF_CSRF_ENABLED=False بـTestConfig، tests/conftest.py) عشان تبسيط
POST المباشر بالاختبارات — هذا الملف وحده يفعّله فعلياً عشان يثبت إن
الحماية شغّالة حقاً، مو موجودة بالكود بس بدون أثر."""
import tempfile
import os

import pytest

import app as app_module
from app.config import Config
from app.extensions import db
from app.models import Role, User
from app.permissions_registry import PERMISSIONS, DEFAULT_ROLES


class CsrfEnabledConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = True
    SECRET_KEY = "test-secret-csrf"
    OWNER_PHONE = "0500000000"
    OWNER_PASSWORD = "test-owner-pass"


@pytest.fixture()
def csrf_app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    CsrfEnabledConfig.SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path}"
    application = app_module.create_app(CsrfEnabledConfig)
    with application.app_context():
        db.create_all()
        from app.models import Permission
        code_to_permission = {}
        for code, description in PERMISSIONS:
            perm = Permission(code=code, description=description)
            db.session.add(perm)
            code_to_permission[code] = perm
        db.session.flush()
        for name, cfg in DEFAULT_ROLES.items():
            role = Role(name=name, display_name=cfg["display_name"], is_system=cfg["is_system"])
            db.session.add(role)
            db.session.flush()
            role.permissions = [code_to_permission[c] for c in cfg["permissions"]]
        db.session.commit()
        role = Role.query.filter_by(name="owner").first()
        owner = User(name="مالك اختبار CSRF", phone="0500000009", role_id=role.id, language="ar")
        owner.set_password("pass1234")
        db.session.add(owner)
        db.session.commit()
        yield application
        db.session.remove()
        db.drop_all()
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture()
def csrf_client(csrf_app):
    return csrf_app.test_client()


def test_login_without_csrf_token_is_rejected(csrf_client):
    resp = csrf_client.post("/login", data={"phone": "0500000009", "password": "pass1234"})
    assert resp.status_code == 400


def test_login_with_valid_csrf_token_succeeds(csrf_client):
    page = csrf_client.get("/login")
    html = page.data.decode()
    start = html.index('name="csrf_token" value="') + len('name="csrf_token" value="')
    token = html[start:html.index('"', start)]

    resp = csrf_client.post(
        "/login", data={"phone": "0500000009", "password": "pass1234", "csrf_token": token},
        follow_redirects=False,
    )
    assert resp.status_code == 302


def test_ajax_task_start_without_csrf_header_is_rejected(csrf_client, csrf_app):
    csrf_client.get("/login")
    page = csrf_client.get("/login")
    html = page.data.decode()
    start = html.index('name="csrf_token" value="') + len('name="csrf_token" value="')
    token = html[start:html.index('"', start)]
    csrf_client.post("/login", data={"phone": "0500000009", "password": "pass1234", "csrf_token": token})

    with csrf_app.app_context():
        from app.team.task_service import assign_task
        owner = User.query.filter_by(phone="0500000009").first()
        task = assign_task(actor=owner, title="مهمة اختبار CSRF", assignee_id=owner.id)
        task_id = task.id

    resp = csrf_client.post(
        f"/team/tasks/{task_id}/start",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 400
