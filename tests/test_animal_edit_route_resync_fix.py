"""فحص "أكواد الحيوانات" — شاشة تعديل حيوان تسمح بتصحيح الجنس/الغرض
(خطأ إدخال شائع)، لكن `ProductionWorkflow.route` (المسار الفعلي اللي
يحدد بوابات دورة الإنتاج — `cycle_engine.determine_route`) كان يُحسب
مرة وحدة عند الإنشاء وما يُعاد حسابه أبداً بعدها. لو صحّحت جنس رأس من
ذكر لأنثى مثلاً، كان يستمر يمشي على مسار "فحل" الخاطئ (بوابات مختلفة
تماماً عن "أنثى مربية") بصمت. الإصلاح: تعديل الجنس/الغرض يعيد حساب
المسار، ولو تغيّر، يُعاد ضبط المرحلة لأول خطوة."""
from app.core import cycle_engine
from app.extensions import db
from tests.factories import make_animal, make_barn


def test_editing_gender_resyncs_stale_production_workflow_route(app, logged_in_client):
    with app.app_context():
        barn = make_barn(barn_no="TIP-EDIT-BARN")
        animal = make_animal(animal_no="TIP-EDIT-1", gender="ذكر", barn_id=barn.id)
        animal.species = "sheep_goat"
        animal.purpose = "تربية"
        db.session.commit()

        wf = cycle_engine.get_or_create_workflow(animal)
        db.session.commit()
        assert wf.route == "male_breeder"

        animal_id, barn_id = animal.id, animal.barn_id

    # تصحيح خطأ إدخال: الرأس فعلياً أنثى
    resp = logged_in_client.post(f"/animals/{animal_id}/edit", data={
        "animal_no": "TIP-EDIT-1", "barn_id": barn_id, "color": "أبيض",
        "gender": "أنثى", "purpose": "تربية", "breed": "عام/غير محدد",
    }, follow_redirects=True)
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "أُعيد تعيين مرحلته" in body

    with app.app_context():
        from app.models import Animal
        refreshed = Animal.query.get(animal_id)
        assert refreshed.gender == "أنثى"
        assert refreshed.workflow.route == "female_breeding"
        assert refreshed.workflow.current_stage == 1
