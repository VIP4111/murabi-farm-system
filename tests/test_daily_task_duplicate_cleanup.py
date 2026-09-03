"""بند إصلاح — بلاغ مستخدم بصورة شاشة توضح نفس المهمة اليومية مكرَّرة
عدة مرات بجدول المهام المعتمدة لعدة أيام متتالية. الإصلاح السابق منع
إضافة قالب جديد بعنوان مكرَّر (شاشة "مهام العامل التلقائية")، بس هذا
ما ينظّف القوالب/المهام المكرَّرة الموجودة أصلاً بقاعدة البيانات —
`flask seed` (يشتغل تلقائياً بكل نشر) صار ينظّفها تلقائياً الآن، بدون
أي خطوة يدوية من المستخدم."""
from datetime import date

from app.extensions import db
from app.models import DailyTaskTemplate, Task


def test_seed_deactivates_duplicate_active_templates(app):
    with app.app_context():
        db.session.add(DailyTaskTemplate(title="مهمة مكررة اختبارية", sort_order=1))
        db.session.add(DailyTaskTemplate(title="مهمة مكررة اختبارية", sort_order=2))
        db.session.add(DailyTaskTemplate(title="مهمة مكررة اختبارية", sort_order=3))
        db.session.commit()

        runner = app.test_cli_runner()
        result = runner.invoke(args=["seed"])
        assert result.exit_code == 0, result.output

        active = DailyTaskTemplate.query.filter_by(
            title="مهمة مكررة اختبارية", is_active=True
        ).all()
        assert len(active) == 1


def test_seed_deletes_duplicate_pending_daily_tasks_but_keeps_in_progress_ones(app):
    today = date.today()
    with app.app_context():
        # 3 نسخ مكرَّرة "قيد الانتظار" بنفس اليوم — لازم يبقى واحدة بس
        for i in range(3):
            db.session.add(Task(
                title="فحص مكرر اختباري", task_type="daily_husbandry", status="pending",
                due_date=today, source_type="DailyHusbandry", source_id=9001 + i,
            ))
        # مهمة "قيد التنفيذ" بنفس العنوان والتاريخ — عمل فعلي حصل، ما لازم تُحذف
        db.session.add(Task(
            title="فحص مكرر اختباري", task_type="daily_husbandry", status="in_progress",
            due_date=today, source_type="DailyHusbandry", source_id=9010,
        ))
        db.session.commit()

        runner = app.test_cli_runner()
        result = runner.invoke(args=["seed"])
        assert result.exit_code == 0, result.output

        remaining = Task.query.filter_by(title="فحص مكرر اختباري", due_date=today).all()
        statuses = sorted(t.status for t in remaining)
        assert statuses == ["in_progress", "pending"]
