"""تقرير أداء الفريق (بند إضافي 229) — نقطة تلقائية موضوعية محسوبة من
بيانات حقيقية (نسبة الإنجاز + الالتزام بالوقت)، بدون أي رقم مخترَع أو
تقييم شخصي بالنقطة نفسها. الأوزان (`COMPLETION_WEIGHT`/`ON_TIME_WEIGHT`)
اجتهاد متّفق عليه معك (50/50) — قابل للتعديل هنا لو حبيت توازناً مختلفاً.

الترجيح الثانوي عند تعادل النقطة (بطلبك الصريح): حجم الشغل الفعلي
(عدد مهام محسومة أكثر يتقدّم) ← سرعة التنفيذ (أسرع يتقدّم) ← عدد
البلاغات المقدَّمة (نشاط إضافي).

تقييم الجودة اليدوي (ضعيف/متوسط/ممتاز، بند إضافي 229 كمان) منفصل
كلياً عن هذي النقطة — إضافي فوقها، مو داخل بمعادلتها، عشان يبقى رأي
بشري صريح مو مخفياً برقم آلي."""
from datetime import datetime, time

from app.models import Task, Report, User

COMPLETION_WEIGHT = 0.5
ON_TIME_WEIGHT = 0.5

QUALITY_LABELS_AR = {"weak": "ضعيف", "medium": "متوسط", "excellent": "ممتاز"}


def worker_performance(*, start_date, end_date) -> list[dict]:
    """يرجّع صف لكل عامل عنده على الأقل مهمة واحدة محسومة (منجزة أو
    متعذّرة) بالفترة، مرتَّبة تنازلياً حسب النقطة."""
    range_start = datetime.combine(start_date, time.min)
    range_end = datetime.combine(end_date, time.max)

    rows = []
    for user in User.query.filter_by(is_active_account=True).order_by(User.name).all():
        completed = Task.query.filter(
            Task.assignee_id == user.id, Task.status == "done",
            Task.completed_at >= range_start, Task.completed_at <= range_end,
        ).all()
        failed = Task.query.filter(
            Task.assignee_id == user.id, Task.status == "failed",
            Task.failed_at >= range_start, Task.failed_at <= range_end,
        ).all()
        resolved_total = len(completed) + len(failed)
        if resolved_total == 0:
            continue

        completion_rate = len(completed) / resolved_total

        with_due = [t for t in completed if t.due_date]
        on_time = [t for t in with_due if t.completed_at.date() <= t.due_date]
        on_time_rate = (len(on_time) / len(with_due)) if with_due else None

        if on_time_rate is None:
            # ما فيه أي مهمة منجزة لها موعد استحقاق بالفترة — النقطة
            # تعتمد على نسبة الإنجاز بس، بدل ما نفترض التزام وقت وهمي.
            score = round(completion_rate * 100, 1)
        else:
            score = round((completion_rate * COMPLETION_WEIGHT + on_time_rate * ON_TIME_WEIGHT) * 100, 1)

        durations = [t.duration_minutes for t in completed if t.duration_minutes]
        avg_duration = round(sum(durations) / len(durations), 1) if durations else None

        reports_count = Report.query.filter(
            Report.reporter_id == user.id,
            Report.created_at >= range_start, Report.created_at <= range_end,
        ).count()

        quality_counts = {"weak": 0, "medium": 0, "excellent": 0}
        weak_notes = []
        for t in completed:
            if t.quality_rating in quality_counts:
                quality_counts[t.quality_rating] += 1
            if t.quality_rating == "weak" and t.quality_rating_note:
                weak_notes.append({"task": t, "note": t.quality_rating_note})

        rows.append({
            "user": user, "score": score,
            "completed_count": len(completed), "failed_count": len(failed),
            "resolved_total": resolved_total, "completion_rate": round(completion_rate * 100, 1),
            "on_time_rate": round(on_time_rate * 100, 1) if on_time_rate is not None else None,
            "avg_duration_minutes": avg_duration,
            "reports_count": reports_count,
            "quality_counts": quality_counts, "weak_notes": weak_notes,
        })

    rows.sort(key=lambda r: (
        -r["score"], -r["resolved_total"],
        r["avg_duration_minutes"] if r["avg_duration_minutes"] is not None else float("inf"),
        -r["reports_count"],
    ))
    return rows


def todays_completed_tasks():
    """كل المهام المنجزة اليوم عبر كل الفريق (بند إضافي 229) — أساس
    شاشة المراجعة اليومية اللي يقدر منها صاحب الحلال/الدكتور/الممرض
    يحطون تقييم جودة يدوي اختياري."""
    from datetime import date as date_cls
    today = date_cls.today()
    range_start = datetime.combine(today, time.min)
    range_end = datetime.combine(today, time.max)
    return (Task.query.filter(
        Task.status == "done", Task.completed_at >= range_start, Task.completed_at <= range_end,
    ).order_by(Task.completed_at.desc()).all())
