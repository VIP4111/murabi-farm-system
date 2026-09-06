"""فحص "سرعة التصفح" — أعمدة تُفلتَر عليها بكل فتحة لصفحة تفاصيل رأس
(`AnimalWeight.animal_id`, `AnimalNote.animal_id`, `MilkRecord.
animal_id`) وبقوائم مهام العامل المقيَّد بحظيرة (`Task.barn_id`) كانت
بدون فهرس قاعدة بيانات — بدون فهرس، PostgreSQL يلجأ لمسح كامل للجدول
كل ما تكبر البيانات المتراكمة (سجل وزن/حليب يتراكم يومياً/أسبوعياً
لكل رأس). هذا الاختبار يتأكد إن الفهرس معرَّف فعلياً بالنموذج (لا
يتحقق من قاعدة بيانات حقيقية — ذاك دور migrations/)."""
from app.models import AnimalWeight, AnimalNote, MilkRecord, Task


def _has_index(model, column_name: str) -> bool:
    col = model.__table__.columns[column_name]
    return bool(col.index)


def test_animal_weight_animal_id_is_indexed():
    assert _has_index(AnimalWeight, "animal_id")


def test_animal_note_animal_id_is_indexed():
    assert _has_index(AnimalNote, "animal_id")


def test_milk_record_animal_id_is_indexed():
    assert _has_index(MilkRecord, "animal_id")


def test_task_barn_id_is_indexed():
    assert _has_index(Task, "barn_id")
