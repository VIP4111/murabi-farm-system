"""طلب صريح: "ضيف فقعات أكثر" — استكمال فقعات الشرح لشاشة "مهام العامل
التلقائية" (السبب الجذري لمشكلة تكرار المهام اليومية اللي أبلغ عنها
المستخدم)."""


def test_daily_templates_page_has_tips(app, logged_in_client):
    resp = logged_in_client.get("/team/tasks/daily-templates")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 2
