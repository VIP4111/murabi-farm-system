"""بند إصلاح — بلاغ مستخدم (حساب الدكتور): شاشة "المهام" مزدحمة/مربكة
("زر اسمه كل المهام دخلت عليه، حصلت لخبطة"). التبسيط:
1. زر "صفحة اليوم" كان اسمه "كل المهام" رغم إنه يفتح شاشة إدارة مهام
   كاملة (4 أقسام) مو بس "بقية مهامي" — أعيد تسميته "إدارة المهام".
2. القسمان الأوسع نطاقاً/الأقل إلحاحاً (جدول كل مهام المزرعة، مهام
   وزّعتها) صارا مطويّين افتراضياً (<details>) بدل ظاهرين دايماً،
   عشان مهامك المباشرة وقسم الاعتماد (الأهم) يبانوا أول شي بدون زحمة."""


def test_today_page_links_to_manage_tasks_not_generic_all_tasks(app, logged_in_client):
    resp = logged_in_client.get("/today")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert "إدارة المهام" in body


def test_tasks_list_wraps_low_priority_sections_in_collapsed_details(app, logged_in_client):
    resp = logged_in_client.get("/team/tasks")
    body = resp.data.decode()
    assert resp.status_code == 200
    # القسمان الأوسع مطويّان بـ<details> بدل بطاقة ظاهرة دايماً
    assert body.count('<details class="drawer-group">') >= 2
    # مهامي وقسم الاعتماد يبقوا خارج الطي (مو داخل <details>)
    assert "مهامي" in body
