"""بند إضافي (2026-08-30) — طلبك الصريح: "بنسبه للارقام ابي لو دخلت
رقم خطأ يرفض من أول ما ادخله يقولي الرقم موجود". قبل هذا البند، تكرار
رقم الحيوان كان يُكتشف بس بعد الضغط على "حفظ" (IntegrityError مُعالَج
بالراوت). الآن فيه فحص فوري إضافي (`/animals/check-number`) يُستدعى
أثناء الكتابة — الحاجز الحقيقي وقت الحفظ يبقى كما هو، هذا تحسين تجربة
استخدام بس."""
from app.core.animal_service import create_animal
from app.models.animal import AnimalSource
from datetime import date
from factories import make_barn


def _make_animal(animal_no):
    return create_animal(
        animal_no=animal_no, source=AnimalSource.PURCHASE, gender="أنثى",
        species="sheep_goat", purchase_date=date.today(),
    )


def test_check_number_reports_exists_true_for_taken_number(app, logged_in_client):
    _make_animal("DUP-01")
    resp = logged_in_client.get("/animals/check-number?animal_no=DUP-01")
    assert resp.status_code == 200
    assert resp.get_json() == {"exists": True}


def test_check_number_reports_exists_false_for_free_number(app, logged_in_client):
    resp = logged_in_client.get("/animals/check-number?animal_no=NOT-TAKEN-99")
    assert resp.status_code == 200
    assert resp.get_json() == {"exists": False}


def test_check_number_with_empty_value_returns_false(app, logged_in_client):
    resp = logged_in_client.get("/animals/check-number?animal_no=")
    assert resp.status_code == 200
    assert resp.get_json() == {"exists": False}


def test_worker_without_animals_manage_permission_forbidden(app, client, worker):
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.get("/animals/check-number?animal_no=DUP-01")
    assert resp.status_code == 403


def test_animal_new_form_includes_live_check_script(app, logged_in_client):
    """تأكيد إن الفورم نفسه فيه سكربت الفحص الفوري (مو بس الراوت
    الخلفي موجود بمعزل)."""
    resp = logged_in_client.get("/animals/new")
    body = resp.data.decode()
    assert "animalNoDupWarning" in body
    assert "check-number" in body


def test_new_animal_creation_still_rejected_server_side_on_real_duplicate(app, logged_in_client):
    """الحاجز الحقيقي (خادم-جانبي) يبقى كما هو حتى لو تجاوز المستخدم
    الفحص الفوري بأي طريقة (مثلاً جافاسكربت معطَّل)."""
    _make_animal("DUP-02")
    make_barn(barn_no="LB-01")
    from app.models import Barn
    barn = Barn.query.filter_by(barn_no="LB-01").first()
    resp = logged_in_client.post("/animals/new", data={
        "animal_no": "DUP-02", "source": "purchase", "gender": "أنثى",
        "barn_id": str(barn.id), "color": "أبيض", "purchase_date": date.today().isoformat(),
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "مستخدم من قبل".encode() in resp.data
