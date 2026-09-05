"""استكمال جولة تدقيق الأداء (بلاغ: "ضعف في التصفح غير سريع") — أكبر
N+1 لقيناها: شاشة "المهام" (على الأرجح أكثر شاشة تُفتح بالنظام).
`task_display_title()` (app/__init__.py) توصل لـ`task.animal`/
`task.barn` لكل صف بكل الجداول الخمسة بالشاشة، وقالب الشاشة يوصل كمان
لـ`task.assignee` — بدون تحميل مسبق، كل صف يسوي استعلامات علاقة منفصلة
له وحده. الإصلاح: `joinedload` مشترك (`_TASK_ROW_EAGER_LOAD`) على
الخمس queries."""
from datetime import date

from sqlalchemy import event

from app.extensions import db
from app.models import Task, Role, User, Barn
from tests.factories import make_animal, make_barn


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


def _seed_tasks_for(worker, prefix, n, barn):
    """مهام مُسنَدة *لعامل واحد بعينه* (worker.id) — عمداً مو صاحب
    الحلال: مودال "توزيع مهمة" (يظهر لمن عنده tasks.assign_any، صاحب
    الحلال دايماً) يجيب مسبقاً كل الحيوانات/الحظائر/العمال دفعة وحدة
    لتعبئة قوائمه — يخفي مشكلة N+1 بالصدفة حتى بدون أي إصلاح. عامل
    عادي بدون هذي الصلاحية يعرض بس "مهامي"، فيكشف المشكلة الحقيقية."""
    for i in range(n):
        animal = make_animal(animal_no=f"{prefix}-{i}", gender="أنثى")
        db.session.flush()
        db.session.add(Task(
            title=f"مهمة {prefix}-{i}", task_type="custom", status="pending",
            due_date=date.today(), assignee_id=worker.id, barn_id=barn.id, animal_id=animal.id,
        ))
    db.session.commit()


def test_tasks_list_query_count_does_not_scale_with_task_count(app, client):
    with app.app_context():
        role = Role.query.filter_by(name="worker").first()
        worker = User(name="عامل اختبار الأداء", phone="0533333333", role_id=role.id)
        worker.set_password("pass1234")
        db.session.add(worker)
        db.session.commit()
        worker_phone = worker.phone
    client.post("/login", data={"phone": worker_phone, "password": "pass1234"})

    def _visit():
        resp = client.get("/team/tasks")
        assert resp.status_code == 200

    with app.app_context():
        barn = make_barn(barn_no="TIP-TL-BARN")
        w = User.query.filter_by(phone=worker_phone).first()
        _seed_tasks_for(w, "TIP-TL-SMALL", 2, barn)
    _, small_queries = _count_select_queries(_visit)

    with app.app_context():
        barn = Barn.query.filter_by(barn_no="TIP-TL-BARN").first()
        w = User.query.filter_by(phone=worker_phone).first()
        _seed_tasks_for(w, "TIP-TL-BIG", 15, barn)
    _, big_queries = _count_select_queries(_visit)

    growth = len(big_queries) - len(small_queries)
    assert growth <= 3, (
        f"عدد استعلامات شاشة المهام كبر مع عدد المهام "
        f"({len(small_queries)} → {len(big_queries)}, فرق {growth}) — احتمال N+1 رجع"
    )
