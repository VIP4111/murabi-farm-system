"""اختبارات بند الفحص العميق للشاشات الجديدة (الأعلاف/النعام):
1. حاسبة العلف كانت تعرض كود الحالة الخام (مثلاً "maintenance") بدل
   الترجمة العربية ("عادي (صيانة)") بجدول النتيجة، رغم إن القائمة
   المنسدلة فوقه تترجمها صح — نفس فئة خلل "كود خام يطلع للمستخدم".
2. جودة بيضة النعام (Egg.quality) تُخزَّن كنص عربي خام ("ممتاز"...)
   وما كانت تمر على gettext بشاشة العرض، فتبقى عربي دائماً لأي لغة
   ثانية بدل ما تُترجم.
"""
from datetime import date

from app.extensions import db
from app.models.ostrich import OstrichEgg
from tests.factories import make_animal, make_barn


def test_feed_calculator_shows_translated_state_not_raw_code(logged_in_client):
    resp = logged_in_client.post("/feed/calculator", data={
        "weight": "40", "state": "growth",
    })
    assert resp.status_code == 200
    assert b">growth<" not in resp.data
    assert "الحالة المستخدمة</td><td>نمو</td>".encode() in resp.data


def test_egg_quality_passes_through_gettext(logged_in_client, app):
    barn = make_barn()
    mother = make_animal(animal_no="OS-01", gender="أنثى", barn_id=barn.id)
    egg = OstrichEgg(mother_id=mother.id, lay_date=date(2026, 1, 1), quality="ممتاز")
    db.session.add(egg)
    db.session.commit()

    resp = logged_in_client.get("/ostrich/eggs")
    assert resp.status_code == 200
    assert "ممتاز".encode() in resp.data
