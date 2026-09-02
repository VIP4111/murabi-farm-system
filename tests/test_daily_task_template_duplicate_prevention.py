"""بند إصلاح — بلاغ مستخدم بصورة شاشة توضح نفس المهمة اليومية
(تنظيف المعالف/فحص الماء/فحص القطيع) مكرَّرة مرتين بجدول المهام
المعتمدة كل يوم. السبب الحقيقي: شاشة "مهام العامل التلقائية" ما كانت
تمنع إضافة قالب بنفس عنوان قالب فعّال موجود أصلاً — كل قالب مكرَّر
يولّد مهمة منفصلة يومياً للأبد (idempotency بـ`daily_task_service`
مبنية على معرّف القالب نفسه، مو على العنوان)."""
from app.models import DailyTaskTemplate
from app.core import daily_task_service


def test_adding_duplicate_active_template_title_is_rejected(app, logged_in_client):
    resp = logged_in_client.post("/team/tasks/daily-templates", data={
        "title": "🧹 تنظيف المعالف والحظائر", "notes": "تكرار اختباري",
    }, follow_redirects=True)
    body = resp.data.decode()
    assert resp.status_code == 200
    assert "فيه مهمة يومية فعّالة بنفس العنوان أصلاً" in body

    with app.app_context():
        count = DailyTaskTemplate.query.filter_by(title="🧹 تنظيف المعالف والحظائر").count()
        assert count == 1


def test_two_active_templates_with_same_title_would_generate_duplicate_tasks(app):
    """يوثّق السبب الجذري نفسه — لو صار (بيانات قديمة قبل الإصلاح)
    قالبان فعّالان بنفس العنوان، يتولّد فعلياً مهمتان منفصلتان بنفس
    اليوم؛ هذا ما يثبت إن المنع أعلاه ضروري فعلياً مو تحسين تجميلي."""
    with app.app_context():
        from app.extensions import db
        db.session.add(DailyTaskTemplate(title="مهمة اختبار مكررة", sort_order=1))
        db.session.add(DailyTaskTemplate(title="مهمة اختبار مكررة", sort_order=2))
        db.session.commit()

        # الدالة تولّد مهام اليوم وأمس معاً (تغطية أي يوم فات بدون
        # فتح الشاشة) — يعني قالبان فعّالان بنفس العنوان = 4 مهام
        # (2 لكل تاريخ)، مو 2 فقط.
        created = daily_task_service.generate_daily_husbandry_tasks()
        titles = [t.title for t in created if t.title == "مهمة اختبار مكررة"]
        assert len(titles) == 4
