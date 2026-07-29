"""اختبارات ترتيب المهام اليومية المنطقي + الترتيب الثانوي الحاسم بالعرض
(بند إضافي 67): تنظيف ← ماء/علف ← فحص قطيع، ومهام بنفس due_date تترتّب
بـsort_order بدل الاعتماد على ترتيب إدراج قاعدة البيانات."""
from app.core import daily_task_service
from app.extensions import db
from app.models import Task


def test_always_rules_generated_in_field_work_order(app):
    daily_task_service.generate_daily_husbandry_tasks()
    tasks = (Task.query.filter_by(source_type="DailyHusbandry")
             .order_by(Task.sort_order).all())
    titles_in_order = [t.title for t in tasks if t.sort_order <= 2]
    # كل تاريخ (أمس/اليوم) عنده نفس الثلاث مهام — نتأكد إن التسلسل صحيح
    # داخل كل يوم على حدة بفحص أول ظهور لكل عنوان
    seen = []
    for t in titles_in_order:
        if t not in seen:
            seen.append(t)
    assert seen[:3] == ["🧹 تنظيف المعالف والحظائر", "💧 فحص الماء والأملاح", "🔍 فحص يومي للقطيع"]


def test_sort_order_field_assigned_sequentially_per_date(app):
    daily_task_service.generate_daily_husbandry_tasks()
    from datetime import date
    today_tasks = (Task.query.filter_by(source_type="DailyHusbandry", due_date=date.today())
                   .order_by(Task.sort_order).all())
    orders = [t.sort_order for t in today_tasks]
    assert orders == sorted(orders)
    assert orders[0] == 0


def test_tasks_list_route_orders_by_due_date_then_sort_order(app, logged_in_client):
    t1 = Task(title="متأخرة الترتيب", task_type="custom", status="suggested",
              due_date=None, sort_order=5)
    t2 = Task(title="أولى بالترتيب", task_type="custom", status="suggested",
              due_date=None, sort_order=1)
    db.session.add_all([t1, t2])
    db.session.commit()

    resp = logged_in_client.get("/team/tasks")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    # نطاق البحث محصور بجدول "مهام مقترحة" بالذات (بند إضافي 69 أضاف
    # نافذة "توزيع مهمة" المنبثقة اللي فيها قائمة منسدلة تسرد كل المهام
    # المفتوحة أيضاً بترتيب مختلف — بحث بكامل الصفحة يلتقط نص القائمة
    # المنسدلة تلك، مو الجدول الفعلي المقصود بهذا الاختبار).
    table_start = body.index("مهام مقترحة")
    table_end = body.index("مهام وزّعتها")
    table = body[table_start:table_end]
    assert table.index("أولى بالترتيب") < table.index("متأخرة الترتيب")


def test_sort_order_defaults_to_zero_for_manually_assigned_tasks(app):
    task = Task(title="مهمة يدوية", task_type="custom", status="pending")
    db.session.add(task)
    db.session.commit()
    assert task.sort_order == 0
