"""دفعة سادسة من طلب "فقعة الشروحات على كل الصفحات" — استمرار توسّع
شاشات القوائم/التقارير: تقرير البيع الذكي (عمود "الدرجة")،
تقرير أداء الفريق (عمود "الالتزام بالوقت")."""


def test_smart_sale_report_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/animals/smart-sale")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'class="info-tip"' in body


def test_performance_report_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/team/performance-report")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'class="info-tip"' in body
