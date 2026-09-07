"""فحص عميق — قسم الدفعات: `create_animal()` تعمل `commit()` فوري لكل
رأس (تصميم مقصود لبقية نقاط الاستدعاء الفردية بالمشروع). كان
`create_batch()` يمرّ على رؤوس الدفعة بحلقة وحدة وينشئ كل رأس فوراً —
لو رأس بمنتصف القائمة فشل التحقق (وزن/سعر غير منطقي)، الرؤوس اللي
قبله كانت أصلاً **محفوظة نهائياً** بقاعدة البيانات قبل ما يوصل الخطأ،
والمستخدم يشوف رسالة خطأ يظن معها إن العملية كلها فشلت — بينما نص
الدفعة انحفظ بصمت بدون علمه."""
import pytest
from datetime import date

from app.core import batch_service
from app.models import AnimalBatch
from tests.factories import make_barn


def test_invalid_entry_midway_creates_no_animals_at_all(app):
    make_barn(barn_no="ISO-ATOM", barn_type="عزل")
    entries = [
        {"animal_no": "ATOM-1", "gender": "أنثى", "color": "أبيض"},
        {"animal_no": "ATOM-2", "gender": "أنثى", "color": "أبيض"},
        # وزن سالب غير منطقي — يفترض يوقف العملية كاملة قبل أي حفظ
        {"animal_no": "ATOM-3", "gender": "أنثى", "color": "أبيض", "weight": -5},
        {"animal_no": "ATOM-4", "gender": "أنثى", "color": "أبيض"},
    ]

    with pytest.raises(ValueError):
        batch_service.create_batch(
            source="purchase", arrival_date=date.today(), notes=None,
            actor_user_id=1, entries=entries,
        )

    assert AnimalBatch.query.count() == 0, "الدفعة انحفظت رغم فشل التحقق على أحد رؤوسها"

    from app.models import Animal
    saved_nos = {a.animal_no for a in Animal.query.filter(Animal.animal_no.like("ATOM-%")).all()}
    assert not saved_nos, (
        f"رؤوس انحفظت جزئياً رغم فشل الدفعة كاملة: {saved_nos} — "
        "إشارة إن الرؤوس السابقة لرأس فشل التحقق تُحفَظ نهائياً قبل ما يوصل الخطأ"
    )
