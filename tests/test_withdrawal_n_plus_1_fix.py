"""بحث "مشاكل تشغيلية" (2026-09-06، جزء ثالث) — أخطر N+1 لقيناها بكامل
الجولة، كلها تُستدعى بكل زيارة تعرض تنبيهات (الرئيسية/سجل الحيوانات/
التنبيهات) وكانت تسوي استعلامات منفصلة *لكل رأس نشط على حدة*:

1. `animal_under_withdrawal`/`animal_under_milk_withdrawal` (3 استعلامات/رأس
   كل وحدة) — استُبدلت بـ`bulk_animal_under_withdrawal`/
   `bulk_animal_under_milk_withdrawal`.
2. `_is_reproductively_delayed` (تنبيه "تأخر شياع"، حتى 4 استعلامات/أنثى
   — أثقل تنبيه بكل الجولة، 61 استعلام فعلياً لـ15 رأس بالقياس) —
   استُبدلت بـ`bulk_is_reproductively_delayed`.
3. `data_completeness_service.generate_completion_tasks` (استعلام مهمة
   مفتوحة منفصل/رأس ناقص) — استُبدل باستعلام IN مجمَّع.
4. `scheduled_care_service.generate_overdue_weight_tasks` (آخر وزن +
   مهمة مفتوحة، كل وحدة منفصلة/رأس) — استُبدلا باستعلامين مجمَّعين."""
from datetime import date

from sqlalchemy import event

from app.extensions import db
from app.health.health_service import bulk_animal_under_withdrawal
from app.core.smart_sale_service import bulk_is_reproductively_delayed
from app.core import data_completeness_service, scheduled_care_service
from app.models import Animal, FarmSettings
from tests.factories import make_animal


def _count_select_queries(fn):
    queries = []

    def _listener(conn, cursor, statement, parameters, context, executemany):
        if statement.strip().upper().startswith("SELECT"):
            queries.append(statement)

    event.listen(db.engine, "before_cursor_execute", _listener)
    try:
        return fn(), queries
    finally:
        event.remove(db.engine, "before_cursor_execute", _listener)


def test_bulk_withdrawal_map_uses_fixed_query_count_regardless_of_animal_count(app):
    with app.app_context():
        ids_small = [make_animal(animal_no=f"TIP-WDB-SMALL-{i}", gender="أنثى").id for i in range(3)]
        _, small_queries = _count_select_queries(lambda: bulk_animal_under_withdrawal(ids_small))

        ids_big = [make_animal(animal_no=f"TIP-WDB-BIG-{i}", gender="أنثى").id for i in range(15)]
        _, big_queries = _count_select_queries(lambda: bulk_animal_under_withdrawal(ids_small + ids_big))

        assert len(small_queries) == len(big_queries) == 3


def test_bulk_delayed_estrus_check_uses_fixed_query_count(app):
    # ملاحظة: `make_animal` تسوي commit داخلياً، فتنتهي صلاحية (expire)
    # كائنات ORM القديمة — الوصول لخاصية معطَّلة يعيد تحميلها باستعلام
    # منفصل (سلوك SQLAlchemy الطبيعي، لا علاقة له بالإصلاح نفسه). نجيب
    # الكائنات "طازجة" بعد إنشاء كلها وقبل قياس الاستعلامات، عشان القياس
    # يعكس فقط استعلامات `bulk_is_reproductively_delayed` نفسها.
    with app.app_context():
        fs = FarmSettings.get()
        small_ids = [make_animal(animal_no=f"TIP-DE-SMALL-{i}", gender="أنثى").id for i in range(3)]
        small = Animal.query.filter(Animal.id.in_(small_ids)).all()
        _, small_queries = _count_select_queries(lambda: bulk_is_reproductively_delayed(small, fs))

        big_ids = small_ids + [make_animal(animal_no=f"TIP-DE-BIG-{i}", gender="أنثى").id for i in range(15)]
        big = Animal.query.filter(Animal.id.in_(big_ids)).all()
        _, big_queries = _count_select_queries(lambda: bulk_is_reproductively_delayed(big, fs))

        # مو تساوٍ تام: `fs` قد يُعاد تحميله باستعلام إضافي واحد بسبب
        # expire-on-commit (نفس ملاحظة `Animal` أعلاه) — المهم إن الفرق
        # لا يتناسب مع عدد الرؤوس (18 رأس هنا، مو فرق بـ4 استعلامات/رأس).
        growth = len(big_queries) - len(small_queries)
        assert growth <= 1, f"استعلامات فحص تأخر الشياع المجمَّع كبرت مع عدد الرؤوس (فرق {growth})"


def test_generate_completion_tasks_query_count_does_not_scale(app):
    """أول استدعاء يُنشئ المهام فعلياً (كتابة حقيقية تتناسب مع عدد
    الرؤوس، هذا طبيعي مو N+1). القياس الحقيقي بثاني استدعاء (idempotent
    — كل المهام موجودة أصلاً)، لأن هنا بالضبط كان فحص "فيه مهمة مفتوحة؟"
    يتكرر لكل رأس."""
    with app.app_context():
        for i in range(3):
            make_animal(animal_no=f"TIP-DC-SMALL-{i}", gender="أنثى")
        data_completeness_service.generate_completion_tasks()  # يُنشئ المهام
        _, small_queries = _count_select_queries(data_completeness_service.generate_completion_tasks)

    with app.app_context():
        for i in range(15):
            make_animal(animal_no=f"TIP-DC-BIG-{i}", gender="أنثى")
        data_completeness_service.generate_completion_tasks()  # يُنشئ المهام
        _, big_queries = _count_select_queries(data_completeness_service.generate_completion_tasks)

    growth = len(big_queries) - len(small_queries)
    assert growth <= 3, f"عدد استعلامات إكمال البيانات كبر مع عدد الرؤوس (فرق {growth}) — احتمال N+1 رجع"


def test_generate_overdue_weight_tasks_query_count_does_not_scale(app):
    """نفس فلسفة الاختبار أعلاه — القياس بثاني استدعاء idempotent."""
    with app.app_context():
        for i in range(3):
            make_animal(animal_no=f"TIP-OW-SMALL-{i}", gender="أنثى")
        scheduled_care_service.generate_overdue_weight_tasks()
        _, small_queries = _count_select_queries(scheduled_care_service.generate_overdue_weight_tasks)

    with app.app_context():
        for i in range(15):
            make_animal(animal_no=f"TIP-OW-BIG-{i}", gender="أنثى")
        scheduled_care_service.generate_overdue_weight_tasks()
        _, big_queries = _count_select_queries(scheduled_care_service.generate_overdue_weight_tasks)

    growth = len(big_queries) - len(small_queries)
    assert growth <= 3, f"عدد استعلامات فحص الأوزان المتأخرة كبر مع عدد الرؤوس (فرق {growth}) — احتمال N+1 رجع"
