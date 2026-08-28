"""بند إضافي 292 — طلبك الصريح "كملها الثلاثة كاملة" بعد فحص صريح
(بند 291) لقينا فيه 3 نقاط تشتت متبقية:
1) كتالوج التحصين (بند 290) بغطاء تسجيل زرع محدود.
2) خريطة الألوان (بند 288) مكرَّرة بـ3 ملفات.
3) مهمتا رش/تحصين الاستقبال مكرَّرتان بمسارين منفصلين (بند 283/286).
هذا الملف يغطي نقطتي 2 و3 (نقطة 1 مغطاة بـtest_vaccine_catalog_seed_coverage_292.py)."""
from datetime import date

from app.core.animal_service import create_intake_care_tasks
from app.models import Task
from factories import make_animal, make_barn


def test_create_intake_care_tasks_is_the_single_shared_entry_point(app):
    """نفس الدالة الوحيدة تُستخدم من `animal_service` و`batch_service`
    الآن — لا يوجد نسخة ثانية من المنطق."""
    from app.core import batch_service
    assert batch_service.create_intake_care_tasks is create_intake_care_tasks


def test_shared_helper_creates_both_tasks_with_custom_label(app):
    animal = make_animal(animal_no="SHARED-01")
    barn = make_barn(barn_no="SHARED-B1")
    spray, vaccination = create_intake_care_tasks(
        animal, barn_id=barn.id, due_date=date.today(),
        source_type="Animal", source_id=animal.id, label="(اختبار مشترك)",
    )
    assert "(اختبار مشترك)" in spray.title
    assert "(اختبار مشترك)" in vaccination.title
    assert spray.task_type == "batch_spray"
    assert vaccination.task_type == "batch_initial_vaccination"
    assert Task.query.filter_by(animal_id=animal.id).count() == 2
