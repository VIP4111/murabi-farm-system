"""بلاغ مستخدم حقيقي: "بطء ممل في تعديل بيانات الحيوانات". السبب: كل
فتحة لشاشة "حيوان جديد"/"تعديل حيوان" كانت تُشغّل
`_seed_system_barns`/`SpeciesType.seed_defaults`/`Breed.seed_defaults`/
`AnimalColor.seed_defaults` من جديد — كل واحدة عدة استعلامات
idempotent-check تسلسلية (١٠+ رحلة قاعدة بيانات بكل فتحة صفحة)، رغم
إنها عملياً ما تحتاج تضيف أي شي بعد أول تشغيل. الإصلاح: علم بمستوى
تطبيق Flask (`current_app.extensions`) يخلي الفحص الحقيقي يصير مرة
وحدة بس لكل تطبيق."""
from unittest.mock import patch

from tests.factories import make_animal


def test_animal_new_form_seeds_options_only_once_per_app(app, logged_in_client):
    with app.app_context():
        from app.core import routes as core_routes
        with patch.object(core_routes, "_seed_system_barns", wraps=core_routes._seed_system_barns) as mocked:
            resp1 = logged_in_client.get("/animals/new")
            assert resp1.status_code == 200
            resp2 = logged_in_client.get("/animals/new")
            assert resp2.status_code == 200
            resp3 = logged_in_client.get("/animals/new")
            assert resp3.status_code == 200
            assert mocked.call_count == 1


def test_animal_edit_form_seeds_options_only_once_per_app(app, logged_in_client):
    with app.app_context():
        a = make_animal(animal_no="TIP-PERF-01")
        animal_id = a.id
        from app.core import routes as core_routes
        with patch.object(core_routes, "_seed_system_barns", wraps=core_routes._seed_system_barns) as mocked:
            resp1 = logged_in_client.get(f"/animals/{animal_id}/edit")
            assert resp1.status_code == 200
            resp2 = logged_in_client.get(f"/animals/{animal_id}/edit")
            assert resp2.status_code == 200
            assert mocked.call_count == 1


def test_animal_form_options_flag_is_per_app_not_global(app):
    """يتأكد إن العلم مربوط بتطبيق Flask نفسه (current_app.extensions)،
    مو متغيّر عالمي بذاكرة العملية — عشان تطبيق ثاني (اختبار آخر بقاعدة
    بيانات جديدة تماماً) ما يتأثر بعلم تطبيق سابق."""
    with app.app_context():
        from flask import current_app
        assert current_app.extensions.get("_animal_form_options_seeded") in (None, False)
