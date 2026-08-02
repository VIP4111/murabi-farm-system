"""بند إضافي 87 — حماية كوكي الجلسة (نقطة 5 من التحليل الثاني). قبل هذا
البند ما كان فيه أي إعداد صريح لـSESSION_COOKIE_SECURE.

ملاحظة: Config._on_render/SESSION_COOKIE_SECURE قيم صف (class-level)
تُحسم عند استيراد app.config لأول مرة — لازم importlib.reload لمحاكاة
بيئة تشغيل مختلفة، مو مجرد monkeypatch للـenv بعد الاستيراد."""
import importlib

import app.config as config_module


def _reload_config(monkeypatch, **env):
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    importlib.reload(config_module)
    return config_module.Config


def test_session_cookie_secure_disabled_by_default_for_local_dev(monkeypatch):
    Config = _reload_config(monkeypatch)
    assert Config.SESSION_COOKIE_SECURE is False


def test_session_cookie_secure_auto_enabled_on_render(monkeypatch):
    Config = _reload_config(monkeypatch, RENDER="true")
    assert Config.SESSION_COOKIE_SECURE is True
    assert Config.REMEMBER_COOKIE_SECURE is True
    importlib.reload(config_module)  # نرجّع الحالة الافتراضية لبقية الاختبارات


def test_session_cookie_samesite_lax(app):
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
