"""فحص عميق — شاشة الإعدادات: `farm_settings_save` كانت تطبّق `int()`/
`float()` على ~40 حقلاً مباشرة على `FarmSettings` بدون أي تحقق سابقاً.
حقل واحد فاضي أو غير رقمي (مسح خطأ، لصق فاضي) يكسر الفورم كله بـ500
خام ويفقد كل التعديلات؛ وقيمة سالبة (خطأ كتابة أو تلاعب بالفورم) كانت
تُقبل بصمت وتكسر حسابات تاريخية حساسة بكل أنحاء النظام (`gestation_
days` سالب مثلاً يخلي "تاريخ الولادة المتوقع" بالماضي)."""
from app.extensions import db
from app.models import FarmSettings
from tests.test_farm_settings_hidden_fields import _base_form


def _full_form(fs):
    """`_base_form` (بند 105) ما يغطي كل حقول الفورم الحالية — نكمّلها
    بباقي الحقول (بند 105 والفئات اللاحقة) بقيمها الحالية، عشان الفورم
    يمر كاملاً بدون رفض بسبب حقل مفقود غير متعلّق بموضوع الاختبار."""
    form = _base_form(fs)
    form.update({
        "quarantine_days": fs.quarantine_days, "reweigh_followup_days": fs.reweigh_followup_days,
        "antiparasitic_redose_days": fs.antiparasitic_redose_days,
        "weight_check_interval_days": fs.weight_check_interval_days,
        "newborn_route_max_age_days": fs.newborn_route_max_age_days,
        "male_fertility_exam_alt_age_days": fs.male_fertility_exam_alt_age_days,
        "weaning_min_age_days": fs.weaning_min_age_days, "weaning_alt_age_days": fs.weaning_alt_age_days,
        "concentrate_increase_window_days": fs.concentrate_increase_window_days,
        "abortion_barn_monitor_days": fs.abortion_barn_monitor_days,
        "concentrate_increase_max_percent_weekly": fs.concentrate_increase_max_percent_weekly,
        "ca_phosphorus_target_ratio": fs.ca_phosphorus_target_ratio,
        "ca_phosphorus_tolerance": fs.ca_phosphorus_tolerance,
    })
    return form


def test_blank_field_rejected_without_crashing_and_saves_nothing(app, logged_in_client):
    fs = FarmSettings.get()
    original_gestation = fs.gestation_days
    form = _full_form(fs)
    form["sponge_duration_days"] = ""  # حقل فاضي (خطأ إدخال شائع)
    form["gestation_days"] = 999  # قيمة صالحة بحقل ثانٍ بنفس الفورم

    resp = logged_in_client.post("/settings/farm", data=form)
    assert resp.status_code == 302  # redirect برسالة خطأ، مو 500 خام

    db.session.refresh(fs)
    # لا شي يُحفَظ جزئياً — حتى الحقول الصالحة بنفس الفورم ترجع بدون تغيير
    assert fs.gestation_days == original_gestation


def test_negative_value_rejected_and_saves_nothing(app, logged_in_client):
    fs = FarmSettings.get()
    original_isolation = fs.isolation_days
    form = _full_form(fs)
    form["gestation_days"] = -5  # قيمة سالبة غير منطقية إطلاقاً
    form["isolation_days"] = 77  # قيمة صالحة بحقل ثانٍ

    resp = logged_in_client.post("/settings/farm", data=form)
    assert resp.status_code == 302

    db.session.refresh(fs)
    assert fs.gestation_days != -5
    assert fs.isolation_days == original_isolation  # ما تحفظ رغم إنها صالحة لحالها


def test_zero_value_is_still_accepted(app, logged_in_client):
    """صفر قيمة مشروعة (تعطيل خاصية زمنية، مثلاً) — الفحص يرفض السالب
    بس، مو الصفر."""
    fs = FarmSettings.get()
    form = _full_form(fs)
    form["workflow_stall_alert_days"] = 0  # حقل موجود بالفورم الأساسي (_base_form)

    resp = logged_in_client.post("/settings/farm", data=form)
    assert resp.status_code == 302

    db.session.refresh(fs)
    assert fs.workflow_stall_alert_days == 0
