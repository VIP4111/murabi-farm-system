"""بند إصلاح (فحص عميق — طلبك: "ابدأ فحص عميق لباقي الشاشات") — رسائل
"reason" بحاسبة العلف وموازِن العليقة (`feed_service.py`) كانت عربي
بحت بدون `_()`، رغم استيراد gettext أصلاً بنفس الملف."""
from app.extensions import db
from app.feed import feed_service
from tests.factories import make_barn
from flask_babel import force_locale


def test_barn_daily_blend_no_weight_reason_translates_to_english(app):
    barn = make_barn(barn_no="EN-FEED-1")
    with force_locale("en"):
        result = feed_service.barn_daily_blend(barn_id=barn.id)
    assert result["feasible"] is False
    assert "weight" in result["reason"].lower()
    assert "وزن" not in result["reason"]


def test_optimize_blend_no_usable_feeds_reason_translates_to_english(app):
    with force_locale("en"):
        result = feed_service.optimize_blend(
            requirement={"daily_dry_matter_kg": 1.0, "target_protein_percent": 12, "target_energy_kcal_per_kg": 2400},
            feeds=[],
        )
    assert result["feasible"] is False
    assert "مكوّنات" not in result["reason"]
