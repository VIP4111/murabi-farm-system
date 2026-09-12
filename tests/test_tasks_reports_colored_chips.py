"""بند إصلاح (تصميم — طلبك: "شاشة المهام/البلاغات" بعد سلسلة تعديلات
الواجهات السابقة) — تبويبات فلترة الدور بشاشة المهام صارت رقاقات
ملوّنة (بدل .tab-btn الرمادي)، ورقم البلاغ بشاشة البلاغات صار شارة
ملوّنة (بدل رابط نص عادي)."""
def test_tasks_role_filter_uses_colored_chip_class(app, logged_in_client):
    resp = logged_in_client.get("/team/tasks")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "role-filter-chip" in html
    assert "--chip-color" in html


def test_reports_list_uses_colored_report_id_chip(app, logged_in_client):
    resp = logged_in_client.get("/team/reports")
    assert resp.status_code == 200
    assert "report-id-chip" in resp.data.decode()
