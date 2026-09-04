"""استكمال إصلاح الأداء بـtest_animal_form_seed_performance.py — نفس
النمط بالضبط لقيناه بعدة مسارات ثانية: `batches_new` (Breed.seed_defaults)،
`team.reports_new` (ReportType.seed_defaults)، و`health.pharmacy_new`/
`pharmacy_edit` (UsageRoute.seed_defaults، مشتركة بينهما بنفس المفتاح)
— كل واحد كان يعيد فحص idempotent-check للقاعدة على كل فتحة صفحة."""
from unittest.mock import patch

from tests.factories import make_pharmacy


def test_batches_new_seeds_breed_defaults_only_once_per_app(app, logged_in_client):
    with app.app_context():
        from app.models import Breed
        with patch.object(Breed, "seed_defaults", wraps=Breed.seed_defaults) as mocked:
            for _ in range(3):
                resp = logged_in_client.get("/batches/new")
                assert resp.status_code == 200
            assert mocked.call_count == 1


def test_reports_new_seeds_report_type_defaults_only_once_per_app(app, logged_in_client):
    with app.app_context():
        from app.models.report_type import ReportType
        with patch.object(ReportType, "seed_defaults", wraps=ReportType.seed_defaults) as mocked:
            for _ in range(3):
                resp = logged_in_client.get("/team/reports/new")
                assert resp.status_code == 200
            assert mocked.call_count == 1


def test_pharmacy_new_and_edit_share_usage_route_seed_guard(app, logged_in_client):
    with app.app_context():
        item = make_pharmacy(name="دواء اختبار الأداء")
        item_id = item.id
        from app.models.usage_route import UsageRoute
        with patch.object(UsageRoute, "seed_defaults", wraps=UsageRoute.seed_defaults) as mocked:
            resp1 = logged_in_client.get("/health/pharmacy/new")
            assert resp1.status_code == 200
            resp2 = logged_in_client.get(f"/health/pharmacy/{item_id}/edit")
            assert resp2.status_code == 200
            resp3 = logged_in_client.get("/health/pharmacy/new")
            assert resp3.status_code == 200
            assert mocked.call_count == 1
