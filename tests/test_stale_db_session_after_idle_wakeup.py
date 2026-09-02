"""بند إصلاح — بلاغ مستخدم: "Internal Server Error" بعد ما يوقف عن
استخدام الموقع فترة (Render المجاني ينام، وقاعدة البيانات — Neon —
تقفل الاتصالات الخاملة). السجل الفعلي اللي أرسله يوضّح
`sqlalchemy.exc.PendingRollbackError: Can't reconnect until invalid
transaction is rolled back` — يعني فحص "تدارك المهام اليومية" اللي
يشتغل بأول كل طلب (`catch_up_daily_tasks_before_request`) واجه خطأ
اتصال (اتصال قديم متقطّع بعد نوم السيرفر)، اتلقط بـ`except Exception`
لكن بدون `rollback()`، فبقيت جلسة SQLAlchemy معطوبة لبقية الطلب —
أي استعلام حقيقي بعدها بنفس الشاشة اللي طلبها المستخدم يفشل بخطأ
سيرفر عام.

الاختبار هنا يبني تطبيق حقيقي (`TESTING=False`) عشان الـ`before_request`
المعني يُسجَّل فعلياً (معطَّل عمداً وقت `TESTING=True` بباقي الاختبارات)،
ويتأكد إن `db.session.rollback()` يُستدعى فعلياً لما فحص التدارك يفشل —
هذا هو الإصلاح الفعلي (رغم إن SQLite بالاختبارات ما يكرّر بالضبط حالة
PendingRollbackError الخاصة بـPostgres/Neon، الاستدعاء الفعلي لـrollback()
هو الضمانة اللي تمنعها على الإنتاج)."""
import os
import tempfile
from unittest.mock import patch

import app as app_module
from app.config import Config
from app.extensions import db
from tests.conftest import _seed_permissions_and_roles, _seed_daily_task_templates


class _RealHookConfig(Config):
    TESTING = False
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret"
    OWNER_PHONE = "0500000000"
    OWNER_PASSWORD = "test-owner-pass"


def test_before_request_hook_rolls_back_session_after_db_failure():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    _RealHookConfig.SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path}"
    application = app_module.create_app(_RealHookConfig)

    with application.app_context():
        db.create_all()
        _seed_permissions_and_roles()
        _seed_daily_task_templates()

    client = application.test_client()

    with patch(
        "app.core.daily_task_service.generate_daily_husbandry_tasks",
        side_effect=RuntimeError("simulated stale DB connection after idle wakeup"),
    ), patch.object(db.session, "rollback") as mock_rollback:
        resp = client.get("/login")
        # الطلب يكمل عادي (200) رغم فشل فحص التدارك — نفس ما يفترض
        # يصير على الإنتاج بفضل rollback() الجديد.
        assert resp.status_code == 200
        # والأهم: rollback() فعلياً انستدعى بعد الفشل، مو مجرد ابتلاع
        # صامت للخطأ زي قبل الإصلاح.
        assert mock_rollback.called

    with application.app_context():
        db.session.remove()
        db.drop_all()
    os.close(db_fd)
    os.unlink(db_path)
