"""بند إضافي 140 — رقم الحيوان والمرحلة بسجل الحيوانات صارا أزرار
(بدل نص/رابط عادي)، بألوان مميّزة (طلبك: "لو تلونها تكون أفضل") —
رقم الحيوان بلون العلامة الأساسي، المرحلة بالأخضر.

بند إصلاح لاحق (تصميم — طلبك: "طبّق هذا التصميم" على سجل الحيوانات
بعد نموذج تجريبي) — الزرّين صار عندهم كلاس تفاعل إضافي
(animal-no-chip/stage-chip: hover/ضغط/focus) وزر المرحلة صار بلون
--t-vax الثابت (بدل .btn.green العام) عشان يتماشى مع نظام الألوان
الجديد لكل قسم — التحديث هنا يعكس الشكل الفعلي الحالي بدل الشكل
القديم."""
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
    assert f'href="/animals/{a.id}"' in body
    assert 'class="btn animal-no-chip"' in body
    assert 'class="btn stage-chip"' in body
    assert "الحجر والفحص" in body
