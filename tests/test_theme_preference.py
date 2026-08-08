"""بند إضافي 158 — وضع ليلي/نهاري شخصي لكل مستخدم، نفس فلسفة تبديل
اللغة (`set_language`) بالضبط."""
from app.extensions import db


def test_new_user_defaults_to_light_theme(app, owner):
    assert owner.theme == "light"


def test_set_theme_to_dark_persists(app, owner, logged_in_client):
    resp = logged_in_client.post("/settings/theme", data={"theme": "dark"}, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(owner)
    assert owner.theme == "dark"


def test_set_theme_rejects_invalid_value(app, owner, logged_in_client):
    logged_in_client.post("/settings/theme", data={"theme": "purple"})
    db.session.refresh(owner)
    assert owner.theme == "light"


def test_html_tag_reflects_saved_theme(app, owner, logged_in_client):
    owner.theme = "dark"
    db.session.commit()
    resp = logged_in_client.get("/")
    body = resp.get_data(as_text=True)
    assert 'data-theme="dark"' in body


def test_html_tag_defaults_to_light_for_new_user(app, logged_in_client):
    resp = logged_in_client.get("/")
    body = resp.get_data(as_text=True)
    assert 'data-theme="light"' in body
