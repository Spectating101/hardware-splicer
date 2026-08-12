from __future__ import annotations

from hardware_splicer.catalog_recipe_pin_audit import audit_catalog_recipe_pins


def test_catalog_recipes_never_reference_pins_that_disappear_before_engine_verification() -> None:
    report = audit_catalog_recipe_pins()

    assert report["status"] == "pass", {
        "blocking_finding_count": report["blocking_finding_count"],
        "findings_by_build": report["findings_by_build"],
    }
    assert report["blocking_finding_count"] == 0
    assert report["checked_endpoint_count"] > 0
    assert report["checks"]["architecture_repair_attempted"] is False
