"""محاكاة تشغيلية لشهر كامل (بند إضافي 180، استُخرجت لدالة قابلة لإعادة
الاستخدام بند إضافي 211) — المنطق نفسه بالضبط اللي كان بأمر CLI
`flask simulate-farm-month`، بدون أي تغيير بالسلوك، فقط منقول لدالة
service عادية عشان تُستدعى من مكانين: أمر الـCLI (كالمعتاد) وزر
"وضع عرض تجريبي" الجديد بشاشة الإعدادات (بند إضافي 211) — بدون تكرار
منطق التوليد.

⚠️ **نفس التحذير الأصلي**: يكتب بيانات فعلية بقاعدة البيانات المتصلة
حالياً — شغّله بس على بيئة تطوير/عرض تجريبي، أبداً على قاعدة إنتاج
فيها بيانات مزرعة حقيقية."""
import random
from datetime import date, timedelta

from flask import current_app
from flask_babel import gettext as _

from app.extensions import db
from app.models import User, Barn, SpeciesType, Breed, AnimalColor, Animal, Mating, Disease
from app.models.animal import AnimalSource
from app.core import animal_service, email_service, telegram_service
from app.team import task_service


def run_farm_month_simulation(days: int = 30, *, send_email: bool = True) -> dict:
    """يرجّع dict: {"ok": bool, "message": str, "body": str, "counters": dict,
    "sent": bool | None}. `send_email=False` (بند إضافي 211، زر الإعدادات)
    يطبع نفس الملخص بدون إرسال بريد فعلي — عكس أمر الـCLI اللي يرسل
    دائماً لصاحب الحلال."""
    notes = []
    random.seed(42)  # نتائج قابلة لإعادة الإنتاج بين تشغيلتين

    owner = User.query.filter_by(phone=current_app.config["OWNER_PHONE"]).first()
    if not owner:
        return {"ok": False, "message": _("ما فيه حساب مالك — شغّل `flask seed` أولاً."), "body": "", "counters": {}, "sent": None}

    barn = Barn.query.first()
    if not barn:
        barn = Barn(barn_no="SIM-1", barn_name="حظيرة المحاكاة", barn_type="عام", capacity=100)
        db.session.add(barn)
        db.session.commit()
        notes.append("ما فيه حظيرة موجودة — أنشأنا حظيرة محاكاة مؤقتة.")

    SpeciesType.seed_defaults()
    Breed.seed_defaults()
    AnimalColor.seed_defaults()
    species = SpeciesType.query.filter_by(code="sheep_goat").first()
    breed = Breed.query.first()
    color = AnimalColor.query.first()
    if not species or not breed or not color:
        return {"ok": False, "message": _("تعذّر تجهيز القوائم المرجعية (فصيلة/سلالة/لون)."), "body": "", "counters": {}, "sent": None}

    today = date.today()
    start_date = today - timedelta(days=days)

    counters = {
        "animals_purchased": 0, "matings": 0, "diseases_opened": 0,
        "diseases_closed": 0, "tasks_created": 0, "tasks_completed": 0,
    }

    def _new_animal(day, gender):
        n = Animal.query.count() + 1
        animal_service.create_animal(
            animal_no=f"SIM-{n:04d}", source=AnimalSource.PURCHASE, gender=gender,
            species="sheep_goat", barn_id=barn.id, purchase_date=day,
            weight=round(random.uniform(20, 45), 1), price=round(random.uniform(400, 900), 2),
            purpose="تربية", color=color.name, breed=breed.name,
        )
        counters["animals_purchased"] += 1

    for offset in range(days):
        day = start_date + timedelta(days=offset)

        if random.random() < 0.2:
            for _ in range(random.randint(1, 2)):
                _new_animal(day, random.choice(["ذكر", "أنثى"]))

        task = task_service.create_suggested_task(
            title=f"🧹 فحص يومي — {day.isoformat()}", task_type="custom",
            barn_id=barn.id, due_date=day,
            source_type="FarmSimulation", source_id=offset,
            auto_approve=True,
        )
        task.assignee_id = owner.id
        db.session.commit()
        counters["tasks_created"] += 1
        if random.random() < 0.75:
            try:
                task_service.complete_task(task, actor=owner, note="محاكاة تشغيلية تلقائية")
                counters["tasks_completed"] += 1
            except Exception as e:  # pragma: no cover - يوثَّق كملاحظة، ما يوقف المحاكاة
                notes.append(f"فشل إنجاز مهمة محاكاة يوم {day}: {e}")

        if random.random() < 0.35:
            females = Animal.query.filter_by(gender="أنثى", status="active").all()
            males = Animal.query.filter_by(gender="ذكر", status="active").all()
            if females and males:
                db.session.add(Mating(
                    female_id=random.choice(females).id, date=day,
                    male_id=random.choice(males).id,
                ))
                counters["matings"] += 1

        if random.random() < 0.2:
            active_animals = Animal.query.filter_by(status="active").all()
            if active_animals:
                animal = random.choice(active_animals)
                disease = Disease(
                    animal_id=animal.id, disease_name="حالة محاكاة عامة",
                    date=day, severity=random.choice(["بسيطة", "متوسطة"]),
                    status="active",
                )
                db.session.add(disease)
                counters["diseases_opened"] += 1
                if random.random() < 0.6:
                    disease.status = "closed"
                    disease.recovery_note = "تعافي — محاكاة تلقائية"
                    disease.closed_at = day
                    counters["diseases_closed"] += 1

        db.session.commit()

    from app.core.animal_profile_service import break_even_summary
    be_rows = break_even_summary()
    at_risk = sum(1 for r in be_rows if r["at_risk"])

    completion_rate = round(
        counters["tasks_completed"] / counters["tasks_created"] * 100, 1
    ) if counters["tasks_created"] else 0

    subject = f"📊 تقرير محاكاة {days} يوم — مراح بو علي"
    body_lines = [
        f"ملخص محاكاة تشغيلية لمدة {days} يوم ({start_date} إلى {today}):",
        "",
        "١) النشاط الميداني:",
        f"- رؤوس مشتراة: {counters['animals_purchased']}",
        f"- عمليات تقريع: {counters['matings']}",
        f"- حالات مرضية فُتحت: {counters['diseases_opened']} (أُغلقت: {counters['diseases_closed']})",
        f"- نسبة إنجاز المهام اليومية: {completion_rate}% ({counters['tasks_completed']}/{counters['tasks_created']})",
        "",
        "٢) التحليل المالي ونقطة التعادل:",
        f"- عدد الرؤوس النشطة المحلَّلة: {len(be_rows)}",
        f"- رؤوس بهامش سالب (خطر خسارة): {at_risk}",
        "",
        "٣) حالة الأتمتة والإشعارات:",
        f"- بريد الإشعارات (Resend): {'مُفعَّل' if email_service._config() else 'غير مُفعَّل (RESEND_API_KEY/EMAIL_FROM_ADDRESS فاضيين)'}",
        f"- تيليجرام: {'مضبوط' if telegram_service._bot_token() else 'غير مضبوط (TELEGRAM_BOT_TOKEN فاضي)'} — هذي المحاكاة ما تستدعي مسارات الإشعار الفوري لكل حدث.",
        "",
        "٤) ملاحظات/ثغرات اكتُشفت أثناء المحاكاة:",
    ]
    if notes:
        body_lines += [f"- {n}" for n in notes]
    else:
        body_lines.append("- ولا ملاحظة — المحاكاة اكتملت بدون أي خطأ.")
    body = "\n".join(body_lines)

    sent = None
    if send_email:
        sent = email_service.notify_user(owner, subject, body)

    return {"ok": True, "message": "", "body": body, "counters": counters, "sent": sent}
