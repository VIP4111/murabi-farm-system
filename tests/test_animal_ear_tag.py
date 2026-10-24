"""بند إضافي 211 — طلبك: "عندي أرقام الحلال بنظام ألوان وأشكال مثل مثلث
ومربع ودائري ومستطيل، لو حبيت تضيف عربي وإنجليزي أو شكل اختار الأفضل".
رقعة الأذن = لون (موجود أصلاً) + شكل من قائمة ثابتة + حرف اختياري
عربي/إنجليزي، تُعرض كرسم SVG بنفس لون الحيوان."""
from app.core.tag_badge import tag_badge
from app.extensions import db
from app.models import Animal
from factories import make_animal, make_barn


def test_shapes_include_users_four_plus_extras():
    for code in ("triangle", "square", "circle", "rectangle"):
        assert code in Animal.TAG_SHAPES
    assert len(Animal.TAG_SHAPES) > 4


def test_clean_shape_and_letter_reject_anything_outside_the_lists():
    assert Animal.clean_tag_shape("triangle") == "triangle"
    assert Animal.clean_tag_shape("hexagon-free-text") is None
    assert Animal.clean_tag_letter("ب") == "ب"
    assert Animal.clean_tag_letter("b") == "B"      # إنجليزي صغير يتحوّل كبير
    assert Animal.clean_tag_letter("بب") is None
    assert Animal.clean_tag_letter("7") is None
    assert Animal.clean_tag_letter("") is None


def test_badge_empty_without_shape_and_drawn_with_it(app):
    assert str(tag_badge(make_animal(animal_no="TG-00"))) == ""
    a = make_animal(animal_no="TG-01")
    a.tag_shape, a.tag_letter, a.color = "triangle", "ب", "أحمر"
    svg = str(tag_badge(a))
    assert "<polygon" in svg and "ب" in svg and "#b3402a" in svg


def test_badge_custom_color_is_grey_dashed(app):
    a = make_animal(animal_no="TG-02")
    a.tag_shape, a.color = "circle", "لون مخصص غريب"
    svg = str(tag_badge(a))
    assert "#d1d5db" in svg and "stroke-dasharray" in svg


def test_create_animal_via_form_stores_shape_and_letter(app, logged_in_client):
    barn = make_barn(barn_no="TG-BARN")
    logged_in_client.post("/animals/new", data={
        "source": "purchase", "gender": "ذكر", "species": "sheep_goat", "color": "أبيض",
        "barn_id": str(barn.id), "animal_no": "TG-10", "tag_shape": "square", "tag_letter": "A",
    })
    a = Animal.query.filter_by(animal_no="TG-10").one()
    assert (a.tag_shape, a.tag_letter) == ("square", "A")


def test_create_animal_via_form_ignores_bogus_shape(app, logged_in_client):
    barn = make_barn(barn_no="TG-BARN2")
    logged_in_client.post("/animals/new", data={
        "source": "purchase", "gender": "ذكر", "species": "sheep_goat", "color": "أبيض",
        "barn_id": str(barn.id), "animal_no": "TG-11", "tag_shape": "<script>", "tag_letter": "zz",
    })
    a = Animal.query.filter_by(animal_no="TG-11").one()
    assert a.tag_shape is None and a.tag_letter is None


def test_edit_form_prefills_and_saves_shape(app, logged_in_client):
    barn = make_barn(barn_no="TG-BARN3")
    a = make_animal(animal_no="TG-12", barn_id=barn.id)
    a.color, a.tag_shape = "أصفر", "oval"
    db.session.commit()
    html = logged_in_client.get(f"/animals/{a.id}/edit").data.decode()
    assert 'id="tagShapeInput" value="oval"' in html
    logged_in_client.post(f"/animals/{a.id}/edit", data={
        "animal_no": "TG-12", "gender": "أنثى", "color": "أصفر", "barn_id": str(barn.id),
        "tag_shape": "star", "tag_letter": "ج",
    })
    db.session.refresh(a)
    assert (a.tag_shape, a.tag_letter) == ("star", "ج")


def test_form_offers_all_shapes_and_both_alphabets(app, logged_in_client):
    html = logged_in_client.get("/animals/new").data.decode()
    for code in Animal.TAG_SHAPES:
        assert f'data-shape="{code}"' in html
    assert '<optgroup label="عربي">' in html and '<optgroup label="English">' in html


def test_badge_shows_in_detail_page(app, logged_in_client):
    barn = make_barn(barn_no="TG-BARN4")
    a = make_animal(animal_no="TG-13", barn_id=barn.id)
    a.color, a.tag_shape, a.tag_letter = "أسود", "diamond", "Z"
    db.session.commit()
    html = logged_in_client.get(f"/animals/{a.id}").data.decode()
    assert 'class="tag-badge"' in html


def test_assistant_explains_ear_tag_shape():
    from app.assistant.knowledge_base import search
    from app.assistant.text_utils import normalize
    for q in ("كيف اضيف شكل الرقعة", "وين اختار شكل رقعة الاذن"):
        results = search(normalize(q))
        assert results and results[0].code == "howto_animal_ear_tag"


# ---- الإدخال الجماعي (طلبك: "ما ضفت الأشكال في الإجراء الجماعي") ----

def test_bulk_purchase_rows_store_shape_and_letter(app, logged_in_client):
    barn = make_barn(barn_no="TG-BULK")
    logged_in_client.post("/animals/bulk-purchase", data={
        "row_count": "2", "purchase_date": "2026-10-01", "species": "sheep_goat", "barn_id": str(barn.id),
        "animal_no_0": "TB-1", "gender_0": "ذكر", "color_0": "أحمر", "tag_shape_0": "triangle", "tag_letter_0": "ب",
        "animal_no_1": "TB-2", "gender_1": "أنثى", "color_1": "أبيض",   # بدون شكل: يبقى فاضي
    })
    a1 = Animal.query.filter_by(animal_no="TB-1").one()
    a2 = Animal.query.filter_by(animal_no="TB-2").one()
    assert (a1.tag_shape, a1.tag_letter) == ("triangle", "ب")
    assert (a2.tag_shape, a2.tag_letter) == (None, None)


def test_bulk_purchase_form_has_shape_and_letter_per_row(app, logged_in_client):
    html = logged_in_client.get("/animals/bulk-purchase").data.decode()
    assert 'name="tag_shape_0"' in html and 'name="tag_letter_7"' in html
    assert 'value="star"' in html
    # قالب الصف الديناميكي (زر "+ إضافة صف") يحمل نفس الحقلين
    assert "TAG_CELL_HTML" in html and "tag_shape___I__" in html


def test_batch_intake_rows_store_shape_and_letter(app, logged_in_client):
    from app.models import AnimalColor
    AnimalColor.seed_defaults()
    resp = logged_in_client.post("/batches/new", data={
        "source": "purchase", "arrival_date": "2026-10-01",
        "animal_no_0": "TB-10", "gender_0": "أنثى", "color_0": "أسود", "tag_shape_0": "diamond", "tag_letter_0": "Z",
    })
    a = Animal.query.filter_by(animal_no="TB-10").one()
    assert (a.tag_shape, a.tag_letter) == ("diamond", "Z")


def test_batch_form_has_shape_and_letter_per_row(app, logged_in_client):
    html = logged_in_client.get("/batches/new").data.decode()
    assert 'name="tag_shape_0"' in html and 'name="tag_letter_0"' in html
