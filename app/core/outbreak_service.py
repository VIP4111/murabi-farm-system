"""رادار كشف تكرار الحالات المرضية بالحظيرة الواحدة (بند إضافي 188،
الجزء 3) — تكامل مع بروتوكول حديث الولادة: تكرار حالات مرضية بنفس
الحظيرة خلال فترة قصيرة إشارة احتمال عدوى منتشرة، مو حادثة معزولة.

**حدود صريحة**: هذا **مؤشر إحصائي بسيط** (عدّاد حالات مفتوحة مختلفة
الرؤوس بنفس الحظيرة خلال نافذة زمنية) — مو تشخيصاً وبائياً حقيقياً،
ومو بديلاً عن تقييم الطبيب لطبيعة الانتشار الفعلي. نفس فلسفة كل
"تحذير" بالمشروع: يلفت الانتباه، القرار يبقى بشري."""
from datetime import date, timedelta
import zlib

from flask_babel import gettext as _, force_locale
from app.models import Disease, Barn, Task
from app.team import task_service

CLUSTER_SOURCE_TYPE = "OutbreakClusterReview"
CLUSTER_WINDOW_DAYS = 7
CLUSTER_THRESHOLD_ANIMALS = 2


def _source_id(barn_id: int, week_number: int) -> int:
    return zlib.crc32(f"outbreak:{barn_id}:{week_number}".encode()) & 0x7FFFFFFF


def detect_barn_clusters(*, today: date | None = None) -> list:
    """يفحص كل حظيرة فيها حالتان مرضيتان مفتوحتان (رأسان مختلفان على
    الأقل) خلال آخر `CLUSTER_WINDOW_DAYS` يوم — لو وُجد، يولّد مهمة
    مراجعة واحدة (idempotent أسبوعياً لكل حظيرة، عشان ما يتكرر يومياً
    لنفس الحالة المستمرة)."""
    today = today or date.today()
    window_start = today - timedelta(days=CLUSTER_WINDOW_DAYS)
    week_number = today.isocalendar()[1]

    created = []
    open_cases = (
        Disease.query.filter(Disease.status == "active", Disease.date >= window_start)
        .join(Disease.animal).all()
    )

    by_barn: dict[int, set] = {}
    for case in open_cases:
        animal = case.animal
        if not animal or not animal.barn_id:
            continue
        by_barn.setdefault(animal.barn_id, set()).add(animal.id)

    for barn_id, animal_ids in by_barn.items():
        if len(animal_ids) < CLUSTER_THRESHOLD_ANIMALS:
            continue
        source_id = _source_id(barn_id, week_number)
        existing = Task.query.filter(
            Task.source_type == CLUSTER_SOURCE_TYPE, Task.source_id == source_id,
            Task.status.in_(task_service.OPEN_TASK_STATUSES),
        ).first()
        if existing:
            continue
        barn = Barn.query.get(barn_id)
        barn_label = barn.display_name() if barn else barn_id
        task = task_service.create_suggested_task(
            title=f"🦠 مراجعة احتمال عدوى منتشرة — حظيرة {barn.barn_name if barn else barn_id}",
            task_type="outbreak_review", barn_id=barn_id,
            due_date=today, source_type=CLUSTER_SOURCE_TYPE, source_id=source_id,
            notes=(
                f"{len(animal_ids)} رأس مختلف بنفس الحظيرة عندهم حالة مرضية مفتوحة خلال آخر "
                f"{CLUSTER_WINDOW_DAYS} يوم — مؤشر إحصائي بس، يستاهل تقييم الطبيب لاحتمال انتشار عدوى."
            ),
        )
        created.append(task)

        # بند إضافي (2026-08-31) — نفس فجوة "تعدد المستلمين بلغات
        # مختلفة" المعالَجة بالتقرير اليومي و submit_report: نص منفصل
        # مبني بلغة كل مستلم فعلياً، بدل نسخة واحدة بلغة مين فتح شاشة
        # التنبيهات (اللي استدعت هذي الدالة، مو المستلمين أنفسهم).
        from app.core import telegram_service, email_service
        from app.models import User
        recipients = [
            u for u in User.query.filter(User.is_active_account.is_(True)).all()
            if u.has_permission("health.manage")
        ]
        for lang in {u.language or "ar" for u in recipients}:
            with force_locale(lang):
                subject = _("🦠 احتمال عدوى منتشرة — حظيرة %(barn)s", barn=barn_label)
                text = subject + "\n" + _(
                    "%(n)s رأس مختلف بنفس الحظيرة بحالة مرضية مفتوحة خلال آخر %(days)s يوم.",
                    n=len(animal_ids), days=CLUSTER_WINDOW_DAYS,
                )
            for user in recipients:
                if (user.language or "ar") != lang:
                    continue
                if user.telegram_chat_id:
                    telegram_service.notify_user(user, text)
                if user.email:
                    email_service.notify_user(user, subject, text)

    return created
