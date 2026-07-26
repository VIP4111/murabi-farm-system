"""
إعداد الاختبارات الآلية (بند إضافي، 2026-07-24) — أول مجموعة اختبارات
حقيقية بالمشروع. قاعدة بيانات SQLite بملف مؤقت منفصلة تماماً عن
farm_system.db الفعلية، تُعاد تهيئتها بالكامل (drop_all/create_all)
قبل كل اختبار عشان كل اختبار يبدأ من صفر بدون أي تسرّب بيانات بين
الاختبارات.
"""
import os
import tempfile

import pytest

import app as app_module
from app.config import Config
from app.extensions import db
from app.models import Role, Permission, User
from app.permissions_registry import PERMISSIONS, DEFAULT_ROLES


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret"
    OWNER_PHONE = "0500000000"
    OWNER_PASSWORD = "test-owner-pass"


@pytest.fixture()
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    TestConfig.SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path}"

    application = app_module.create_app(TestConfig)

    with application.app_context():
        db.create_all()
        _seed_permissions_and_roles()
        yield application
        db.session.remove()
        db.drop_all()

    os.close(db_fd)
    os.unlink(db_path)


def _seed_permissions_and_roles():
    """نفس منطق `flask seed` (app/cli.py) بس مباشر بدون آلية Click —
    أسرع وأبسط لسياق الاختبارات."""
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


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def owner(app):
    role = Role.query.filter_by(name="owner").first()
    user = User(name="مالك الاختبار", phone="0500000001", role_id=role.id, language="ar")
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture()
def worker(app):
    """عامل بدون animals.view — نفس تعريف دور العامل الافتراضي، يُستخدم
    لاختبار تقييد الحظائر (بند 46، القسم 5)."""
    role = Role.query.filter_by(name="worker").first()
    user = User(name="عامل الاختبار", phone="0500000002", role_id=role.id, language="ar")
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture()
def logged_in_client(client, owner):
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    return client
