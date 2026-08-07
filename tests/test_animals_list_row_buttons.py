"""بند إضافي 140 — رقم الحيوان والمرحلة بسجل الحيوانات صارا أزرار
(بدل نص/رابط عادي)، بألوان مميّزة (طلبك: "لو تلونها تكون أفضل") —
رقم الحيوان بلون العلامة الأساسي، المرحلة بالأخضر."""
from datetime import date

from app.extensions import db
from factories import make_animal


def test_animal_number_and_stage_render_as_colored_buttons(logged_in_client):
    a = make_animal(animal_no="ROWBTN-01")
    a.lifecycle_stage = "الحجر والفحص"
    db.session.commit()

    resp = logged_in_client.get("/animals")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert f'class="btn" style="padding:4px 10px; font-size:13px;" href="/animals/{a.id}"' in body
    assert 'class="btn green"' in body
    assert "الحجر والفحص" in body
