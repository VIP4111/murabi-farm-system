"""بند إضافي 105 — 8 إعدادات زمنية كانت مخزَّنة بقاعدة البيانات وتُستخدم
فعلياً بالنظام (حجر، إعادة وزن، جرعات، تغذية، مراقبة إجهاض)، بدون أي
شاشة تعديل — الطريقة الوحيدة لتغييرها كانت التعديل المباشر بقاعدة
البيانات."""
from app.extensions import db
from app.models import FarmSettings


def _base_form(fs):
    """كل الحقول الموجودة أصلاً بالفورم (غير بند 105) بقيمها الحالية،
    عشان الفورم كامل يمر بدون KeyError."""
    return {
        "gestation_days": fs.gestation_days, "sponge_duration_days": fs.sponge_duration_days,
        "ram_entry_after_sponge_days": fs.ram_entry_after_sponge_days,
        "pre_birth_feed_change_days": fs.pre_birth_feed_change_days,
        "postpartum_feed_days": fs.postpartum_feed_days,
        "male_sale_after_birth_days": fs.male_sale_after_birth_days,
        "alert_before_days": fs.alert_before_days, "vaccination_repeat_days": fs.vaccination_repeat_days,
        "isolation_days": fs.isolation_days, "doctor_check_hours": fs.doctor_check_hours,
        "postpartum_vaccination_days": fs.postpartum_vaccination_days,
        "min_breeding_age_days": fs.min_breeding_age_days,
        "min_rest_after_birth_days": fs.min_rest_after_birth_days,
        "target_profit_margin_percent": fs.target_profit_margin_percent,
        "regular_sale_age_days": fs.regular_sale_age_days, "udhiyah_min_age_days": fs.udhiyah_min_age_days,
        "female_delayed_conception_days": fs.female_delayed_conception_days,
        "report_stale_hours": fs.report_stale_hours, "ostrich_incubation_days": fs.ostrich_incubation_days,
        "workflow_stall_alert_days": fs.workflow_stall_alert_days,
        "colostrum_window_hours": fs.colostrum_window_hours,
        "placenta_check_hours": fs.placenta_check_hours,
        "postpartum_mother_followup_days": fs.postpartum_mother_followup_days,
    }


def test_save_updates_previously_hidden_fields(app, logged_in_client):
    fs = FarmSettings.get()
    form = _base_form(fs)
    form.update({
        "quarantine_days": 30,
        "reweigh_followup_days": 21,
        "antiparasitic_redose_days": 45,
        "concentrate_increase_max_percent_weekly": 15.5,
        "concentrate_increase_window_days": 10,
        "ca_phosphorus_target_ratio": 2.5,
        "ca_phosphorus_tolerance": 0.75,
        "abortion_barn_monitor_days": 20,
        "weight_check_interval_days": 25,
        "newborn_route_max_age_days": 100,
        "male_fertility_exam_alt_age_days": 150,
        "weaning_min_age_days": 45,
        "weaning_alt_age_days": 75,
    })
    resp = logged_in_client.post("/settings/farm", data=form)
    assert resp.status_code == 302

    db.session.refresh(fs)
    assert fs.quarantine_days == 30
    assert fs.reweigh_followup_days == 21
    assert fs.antiparasitic_redose_days == 45
    assert fs.concentrate_increase_max_percent_weekly == 15.5
    assert fs.concentrate_increase_window_days == 10
    assert fs.ca_phosphorus_target_ratio == 2.5
    assert fs.ca_phosphorus_tolerance == 0.75
    assert fs.abortion_barn_monitor_days == 20


def test_settings_page_renders_new_fields(app, logged_in_client):
    resp = logged_in_client.get("/settings")
    body = resp.data.decode()
    for field in (
        "quarantine_days", "reweigh_followup_days", "antiparasitic_redose_days",
        "concentrate_increase_max_percent_weekly", "concentrate_increase_window_days",
        "ca_phosphorus_target_ratio", "ca_phosphorus_tolerance", "abortion_barn_monitor_days",
    ):
        assert f'name="{field}"' in body
