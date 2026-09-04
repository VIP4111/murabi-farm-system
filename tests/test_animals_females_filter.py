"""بلاغ مستخدم مع صورة شاشة: "عندي ذكر وعندي انثى حصلت اذكر وما حصبت
الانثا في اشريط العلوي" — تبويب "الذكور" موجود بشريط فلاتر سجل
الحيوانات، بس ما فيه تبويب "الإناث" أصلاً بـFILTERS (نقص حقيقي بالكود،
مو مجرد قص بالصورة)."""
from app.core.animal_filters_service import FILTERS, get_filtered
from tests.factories import make_animal


def test_females_filter_registered_in_filters_dict():
    assert "females" in FILTERS
    label, _fn = FILTERS["females"]
    assert str(label) == "الإناث"


def test_females_filter_returns_only_active_females(app):
    with app.app_context():
        make_animal(animal_no="TIP-M-01", gender="ذكر")
        f1 = make_animal(animal_no="TIP-F-01", gender="أنثى")
        f2 = make_animal(animal_no="TIP-F-02", gender="أنثى")
        rows = get_filtered("females")
        assert {a.id for a in rows} == {f1.id, f2.id}


def test_animals_list_shows_females_tab(app, logged_in_client):
    with app.app_context():
        make_animal(animal_no="TIP-F-03", gender="أنثى")
    resp = logged_in_client.get("/animals")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert "الإناث" in body
    assert 'filter=females' in body
