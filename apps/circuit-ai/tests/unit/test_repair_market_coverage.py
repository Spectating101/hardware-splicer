from src.intelligence.repair_market_coverage import RepairMarketCoverage


def test_market_coverage_scores_strong_small_usb_gadget_fit():
    result = RepairMarketCoverage().evaluate_text("Fixing a USB desk fan that will not spin")

    top = result["top_matches"][0]
    assert top["item_id"] == "small_usb_gadget"
    assert top["coverage_level"] == "strong"
    assert result["matched"] is True


def test_market_coverage_marks_phone_as_partial_or_weak():
    result = RepairMarketCoverage().evaluate_text("iPhone charging port board repair")

    top = result["top_matches"][0]
    assert top["item_id"] == "phone_or_tablet"
    assert top["coverage"] < 0.5
    assert "Do not sell" in result["recommendation"] or "Research/prototype" in result["recommendation"]


def test_market_coverage_scores_new_real_case_lanes():
    coverage = RepairMarketCoverage()

    controller = coverage.evaluate_text("Xbox controller stick drift repair")
    assert controller["top_matches"][0]["item_id"] == "game_controller"
    assert controller["top_matches"][0]["coverage"] >= 0.7

    toothbrush = coverage.evaluate_text("electric toothbrush not charging dock battery")
    assert toothbrush["top_matches"][0]["item_id"] == "battery_charging_gadget"

    tv = coverage.evaluate_text("TV has sound but no picture backlight")
    assert tv["top_matches"][0]["item_id"] == "tv_monitor_backlight"


def test_market_coverage_portfolio_prioritizes_strong_electronics_lanes():
    portfolio = RepairMarketCoverage().portfolio()

    assert portfolio["summary"]["strong_count"] >= 2
    assert portfolio["summary"]["weighted_coverage"] > 0.45
    labels = {item["item_id"] for item in portfolio["strong_fit"]}
    assert "small_usb_gadget" in labels
    assert "retro_handheld_console" in labels
