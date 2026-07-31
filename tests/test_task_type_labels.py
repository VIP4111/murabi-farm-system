"""اختبارات تصحيحات شاشة المهام (بند إضافي 66): ترجمة نوع المهمة لعربي
بدل النص الخام، حقل التاريخ RTL، ومحاذاة الأزرار."""
def test_daily_husbandry_type_shows_arabic_label_not_raw_string(app, logged_in_client):
    from app.core import daily_task_service
    daily_task_service.generate_daily_husbandry_tasks()
    resp = logged_in_client.get("/team/tasks")
    assert resp.status_code == 200
    assert b"daily_husbandry" not in resp.data
    assert "رعاية يومية".encode() in resp.data


def test_ar_task_type_filter_maps_known_values(app):
    # قيم TASK_TYPE_LABELS_AR صارت _l() (بند إضافي 74) — تحتاج سياق طلب
    # حقيقي عشان تُحسم للغة (select_locale يقرأ session/current_user).
    filt = app.jinja_env.filters["ar_task_type"]
    with app.test_request_context():
        assert filt("daily_husbandry") == "رعاية يومية"
        assert filt("move_to_pregnant_barn") == "نقل لحظيرة الحوامل"
        assert filt("batch_spray") == "رش وقائي (دفعة)"


def test_ar_task_type_filter_falls_back_to_raw_value_for_unknown_type(app):
    filt = app.jinja_env.filters["ar_task_type"]
    assert filt("some_future_type_not_mapped_yet") == "some_future_type_not_mapped_yet"


def test_tasks_list_page_has_no_broken_date_input_direction(app, logged_in_client):
    """يتأكد إن قاعدة CSS الجديدة لحقول التاريخ موجودة فعلاً بالصفحة
    (بند 66) — التحقق الفعلي من اتجاه العرض بالمتصفح صار حياً بمتصفح
    فعلي أثناء التطوير، هذا اختبار وجود القاعدة بس."""
    resp = logged_in_client.get("/team/tasks")
    assert resp.status_code == 200
    assert b'input[type="date"]' in resp.data
    assert b"direction:ltr" in resp.data
