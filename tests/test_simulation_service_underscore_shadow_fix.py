"""بحث "افحص جميع الأكواد" (تحليل ثابت بـpyflakes) — `run_farm_month_
simulation` فيها `for _ in range(...)` بمنتصف الدالة، وبأعلى الملف
`from flask_babel import gettext as _`. بايثون يعتبر `_` متغيّراً
محلياً بكامل الدالة بمجرد وجود أي إسناد له بداخلها (حتى متغيّر حلقة
for) — فأي استدعاء `_(...)` *قبل* الحلقة بنفس الدالة (زي رسائل الخطأ
المبكرة هنا) يطلّع UnboundLocalError فوراً بدل الرسالة العربية
المقصودة، لأن بايثون يعتبره "محلي لسا ما انعطى قيمة" مو الدالة
المستوردة. يظهر فعلياً أول ما تشتغل المحاكاة على قاعدة بدون حساب
مالك (بالضبط الحالة اللي الرسالة نفسها تفترض إنها تتعامل معها)."""
from app.core.simulation_service import run_farm_month_simulation


def test_simulation_without_owner_returns_friendly_message_not_crash(app):
    """قاعدة بدون حساب مالك (`flask seed` ما اشتغل) — لازم يرجّع رسالة
    عربية واضحة، مو UnboundLocalError."""
    with app.app_context():
        result = run_farm_month_simulation(days=1, send_email=False)
        assert result["ok"] is False
        assert "حساب مالك" in result["message"]
