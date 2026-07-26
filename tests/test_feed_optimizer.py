"""اختبارات موازِن العليقة (البرمجة الخطية) — بند إضافي 48، القسم
الثاني-٢."""
from app.feed.feed_service import optimize_blend, daily_requirement
from factories import make_feed


def test_optimizer_meets_protein_and_energy_targets(app):
    make_feed(name="برسيم", unit_price=1.5, protein_percent=18, energy_kcal_per_kg=2400, available_qty=100)
    make_feed(name="شعير", unit_price=1.0, protein_percent=11, energy_kcal_per_kg=3000, available_qty=100)
    make_feed(name="تبن", unit_price=0.5, protein_percent=4, energy_kcal_per_kg=1800, available_qty=100)

    from app.models import Feed
    feeds = Feed.query.all()
    requirement = daily_requirement(weight_kg=40, state="growth")
    result = optimize_blend(requirement=requirement, feeds=feeds)

    assert result["feasible"] is True
    total_qty = sum(b["quantity_kg"] for b in result["blend"])
    assert abs(total_qty - requirement["daily_dry_matter_kg"]) < 0.01

    # قيد بروتين النموذج الأصلي: sum(protein_i/100 * x_i) >= target/100 * dmi
    # بضرب الطرفين ×100: sum(protein_i * x_i) >= target_protein * dmi
    weighted_protein = sum(b["quantity_kg"] * next(f.protein_percent for f in feeds if f.name == b["feed"].name) for b in result["blend"])
    required_protein = requirement["target_protein_percent"] * requirement["daily_dry_matter_kg"]
    assert weighted_protein >= required_protein - 0.1


def test_optimizer_picks_cheapest_feasible_blend(app):
    # مكوّن واحد يغطي الاحتياج بالكامل وأرخص من غيره -> يجب يهيمن (لحد سقف max_fraction)
    make_feed(name="رخيص عالي بروتين", unit_price=0.5, protein_percent=20, energy_kcal_per_kg=3000, available_qty=100)
    make_feed(name="غالي", unit_price=5.0, protein_percent=20, energy_kcal_per_kg=3000, available_qty=100)

    from app.models import Feed
    feeds = Feed.query.all()
    requirement = daily_requirement(weight_kg=40, state="maintenance")
    result = optimize_blend(requirement=requirement, feeds=feeds)

    assert result["feasible"] is True
    cheap_row = next(b for b in result["blend"] if b["feed"].name == "رخيص عالي بروتين")
    assert cheap_row["percent"] >= 59  # يهيمن لحد سقف 60% الافتراضي
    assert result["total_daily_cost"] < 5 * requirement["daily_dry_matter_kg"]


def test_optimizer_infeasible_when_no_high_protein_feed_available(app):
    make_feed(name="تبن ضعيف", unit_price=0.3, protein_percent=2, energy_kcal_per_kg=1500, available_qty=100)
    from app.models import Feed
    feeds = Feed.query.all()
    requirement = daily_requirement(weight_kg=40, state="lactation")  # هدف بروتين عالي (16%)
    result = optimize_blend(requirement=requirement, feeds=feeds)
    assert result["feasible"] is False
    assert "reason" in result


def test_optimizer_no_usable_feeds_returns_infeasible(app):
    make_feed(name="بدون بيانات كافية", unit_price=None)
    from app.models import Feed
    feeds = Feed.query.all()
    requirement = daily_requirement(weight_kg=40, state="maintenance")
    result = optimize_blend(requirement=requirement, feeds=feeds)
    assert result["feasible"] is False


def test_optimizer_flags_insufficient_stock(app):
    make_feed(name="نادر", unit_price=1.0, protein_percent=20, energy_kcal_per_kg=3000, available_qty=0.01)
    from app.models import Feed
    feeds = Feed.query.all()
    requirement = daily_requirement(weight_kg=40, state="maintenance")
    result = optimize_blend(requirement=requirement, feeds=feeds)
    assert result["feasible"] is True
    assert result["all_stock_ok"] is False
