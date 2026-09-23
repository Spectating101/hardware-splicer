from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "experiments" / "product_factory" / "evaluate_supply_route.py"
SPEC = importlib.util.spec_from_file_location("pf_supply_probe", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

ROUTE = json.loads(
    (ROOT / "experiments" / "product_factory" / "donor_probes" / "benchnode_v0_supply_route.json").read_text()
)


def test_benchnode_probe_has_attractive_hypothetical_economics_but_holds_on_supply() -> None:
    result = MODULE.evaluate_supply_route(ROUTE)
    assert result["effective_cogs_per_sellable_usd"] < 85
    assert result["gross_margin_fraction"] >= ROUTE["minimum_target_gross_margin_fraction"]
    assert result["savings_vs_all_new_fraction"] >= ROUTE["minimum_donor_savings_fraction"]
    assert result["decision"] == "HOLD_SUPPLY_ROUTE"
    assert result["checks"]["supply_depth"] is False
    assert "supply_depth" in result["blockers"]


def test_benchnode_does_not_get_physical_authority_from_good_paper_economics() -> None:
    result = MODULE.evaluate_supply_route(ROUTE)
    assert result["authority"]["physical_rework_authorized"] is False
    assert result["authority"]["fabrication_authorized"] is False
