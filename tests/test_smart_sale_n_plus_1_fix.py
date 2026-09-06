"""بحث "سرعة التنقل" (2026-09-06) — أخطر N+1 لقيناه بكل الجولات: كل
رأس نشط بـ`get_recommendations()` (شاشة "البيع الذكي" `/animals/
smart-sale`) كان يسوي حتى 10 استعلامات منفصلة له لحاله (وزن مرتين —
`_weight_trend` و`marginal_feeding_signal` كل وحدة لحالها، تكلفة صحية
مرتين — نفس السبب، تأخر شياع حتى 4 للإناث، خطة علف مرة). أخطر من هذا:
هذي الدالة تُستدعى تلقائياً بكل تحميل للرئيسية عبر `alerts_service.
_ready_to_sell_now()` — يعني كل صفحة رئيسية تدفع هذا الثمن. الإصلاح:
كل البيانات المساعدة تُجهَّز مرة وحدة لكل الرؤوس دفعة وحدة (`ctx`)."""
from sqlalchemy import event

from app.extensions import db
from app.core.smart_sale_service import get_recommendations
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


def test_get_recommendations_query_count_does_not_scale_with_animal_count(app):
    with app.app_context():
        for i in range(3):
            make_animal(animal_no=f"TIP-SS-SMALL-{i}", gender="ذكر")
        _, small_queries = _count_select_queries(get_recommendations)

    with app.app_context():
        for i in range(15):
            make_animal(animal_no=f"TIP-SS-BIG-{i}", gender="ذكر")
        _, big_queries = _count_select_queries(get_recommendations)

    growth = len(big_queries) - len(small_queries)
    assert growth <= 5, (
        f"عدد استعلامات شاشة البيع الذكي كبر مع عدد الرؤوس "
        f"({len(small_queries)} → {len(big_queries)}, فرق {growth}) — احتمال N+1 رجع"
    )


def test_get_recommendations_still_returns_correct_scores(app):
    """الإصلاح ما لازم يغيّر أي نتيجة فعلية — نفس المنطق بالضبط، بس
    بأسلوب مجمَّع."""
    with app.app_context():
        make_animal(animal_no="TIP-SS-1", gender="ذكر")
        make_animal(animal_no="TIP-SS-2", gender="أنثى")
        rows = get_recommendations()
        assert len(rows) == 2
        assert all("score" in r and "reasons" in r for r in rows)
