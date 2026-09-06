"""مراجعة "أكواد الخلفية" (استكمال) — `daily_task_service._build_
context()` كانت تحسب `today` الخاص فيها بشكل مستقل عبر `date.today()`
الخام (توقيت السيرفر، UTC)، بدل استخدام نفس `today` (المشتق من `now`
اللي يُمرَّر بتوقيت السعودية عبر `farm_now_naive()` من `scheduler.py`/
`alerts_service.py`) المحسوب أصلاً بـ`generate_daily_husbandry_tasks`.

تناقض داخلي حقيقي: نفس استدعاء الدالة، جزء من منطقها (تواريخ المهام
نفسها) يعتمد يوم السعودية الصحيح، وجزء ثانٍ (هل فيه مواليد/فطام/شراء
حديث — تحدّد أي مهام تُولَّد أصلاً) يعتمد يوم UTC. قرب منتصف الليل
بالسعودية هذا يعني قرار "هل نولّد مهمة متابعة مواليد اليوم؟" ممكن يُبنى
على تاريخ يوم مختلف تماماً عن تاريخ استحقاق المهمة نفسها."""
from datetime import date, timedelta, datetime as dt

from app.extensions import db
from app.core import daily_task_service
from tests.factories import make_animal


def test_build_context_newborn_window_uses_passed_today_not_raw_utc_today(app, monkeypatch):
    with app.app_context():
        # لو الكود القديم (`date.today()` الخام) يشتغل، بيرجّع تاريخ
        # التشغيل الحقيقي لهذا الاختبار (اليوم الفعلي بالنظام) — بعيد
        # عمداً عن `fake_now` تحت (سنوات فرق)، فيحسب فرق أيام أكبر بكثير
        # من 30 (يفشل شرط "مولود حديث") بغض النظر عن تاريخ التشغيل الفعلي.
        fake_now = dt(2020, 1, 15, 12, 0)
        birth_date = fake_now.date() - timedelta(days=10)  # مولود عمره 10 أيام بالنسبة لـfake_now

        animal = make_animal(animal_no="TIP-CTX-TZ")
        animal.birth_date = birth_date
        db.session.commit()

        created = daily_task_service.generate_daily_husbandry_tasks(now=fake_now)
        titles = [t.title for t in created]
        assert any("متابعة المواليد" in t for t in titles), (
            "مهمة متابعة المواليد ما تولّدت رغم إن المولود عمره 10 أيام فقط "
            "بالنسبة لـ`now` الممرَّر — إشارة إن `_build_context` حسبت "
            "تاريخها الخاص بدل استخدام نفس `today`."
        )
