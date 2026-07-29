"""بند إضافي 73 (2026-07-29): رابط "آمن"/فترة السحب بصفحة سجل الحيوانات
لتفاصيل الرأس، وأزرار "انتقل للمكان المقصود" لكل متطلب ناقص بصفحة دورة
الإنتاج. النطاق مقصود: نختبر التطابق (وعدم التطابق) لدالة الخريطة
مباشرة، وربطها الفعلي بصفحة دورة الإنتاج، ووجود رابط تفاصيل الرأس حول
شارة "آمن"/فترة السحب بصفحة سجل الحيوانات."""
from app.core.routes import _missing_item_action
from factories import make_animal


def test_missing_item_action_matches_health_evidence_requirement(app):
    with app.test_request_context():
        label, url = _missing_item_action("فحص صحي أو زيارة بيطرية أو تطعيم", 7)
    assert label == "زيارة بيطرية ←"
    assert url == "/health/vet-visits/new?animal_id=7"


def test_missing_item_action_matches_quarantine_requirement_with_dynamic_number(app):
    with app.test_request_context():
        result = _missing_item_action("فترة حجر 21 يوم من الدخول (باقي 21 يوم)", 7)
    assert result is not None
    label, url = result
    assert label == "تفاصيل الرأس ←"
    assert url == "/animals/7"


def test_missing_item_action_returns_none_for_unmapped_requirement(app):
    with app.test_request_context():
        assert _missing_item_action("تشخيص حمل أو فحص سونار", 7) is None


def test_animal_workflow_page_shows_action_buttons_for_known_requirements(logged_in_client, app):
    animal = make_animal(animal_no="W-01")
    resp = logged_in_client.get(f"/animals/{animal.id}/workflow")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "فحص صحي أو زيارة بيطرية أو تطعيم" in html
    assert "فترة حجر" in html
    assert f'/health/vet-visits/new?animal_id={animal.id}' in html
    assert f'href="/animals/{animal.id}"' in html


def test_animals_list_safe_badge_links_to_animal_detail(logged_in_client, app):
    animal = make_animal(animal_no="W-02")
    resp = logged_in_client.get("/animals")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    idx = html.index(f'href="/animals/{animal.id}" style="text-decoration:none;"')
    surrounding = html[idx: idx + 250]
    assert "آمن" in surrounding
