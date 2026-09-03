"""طلب صريح متكرر: "أكمل فقعات" — استكمال فقعات الشرح لشاشة "الصيدلية"
(جدول كثيف بـ11 عمود، أعمدة مصطلحات فنية زي "نفاد متوقع" و"سحب لحم/ذبح")."""


def test_pharmacy_list_has_tips(app, logged_in_client):
    resp = logged_in_client.get("/health/pharmacy")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 4
