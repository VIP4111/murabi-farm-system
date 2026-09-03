"""طلب صريح متكرر: "أكمل فقعات" — استكمال فقعات الشرح لشاشة "مكوّنات
العلف" (نفس نمط الصيدلية — مصطلحات غذائية: فئة العلف، بروتين%،
نفاد متوقع)."""


def test_feed_items_list_has_tips(app, logged_in_client):
    resp = logged_in_client.get("/feed/items")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 3
