from __future__ import annotations

from hardware_splicer.integrations.oss_catalog import integration_catalog


def test_catalog_exposes_the_joined_product_workflow() -> None:
    payload = integration_catalog()
    rows = {row["id"]: row for row in payload["integrations"]}

    studio = rows["capability-studio"]
    assert studio["status"] == "wired"
    assert studio["url"] == "/capability-studio.html"
    assert "inspect → compile → engineering review → handoff" in studio["hook"]

    circuit_json = rows["circuit-json"]
    assert circuit_json["status"] == "wired"
    assert "source components, ports, nets, traces" in circuit_json["claim"]

    review = rows["kicad-happy"]
    assert review["status"] == "opt_in"
    assert "observed-only authority" in review["claim"]
