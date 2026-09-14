#!/usr/bin/env python3
"""Run the Derived Virtual Lab RC sweep and selected ngspice cross-checks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
src_root = str(SRC_ROOT)
while src_root in sys.path:
    sys.path.remove(src_root)
sys.path.insert(0, src_root)

from hardware_splicer.spi_derived_rc_spice import (  # noqa: E402
    build_rc_sweep,
    run_rc_spice_crosscheck,
)

CROSSCHECK_CASES = (
    {"rail_v": 1.800, "series_resistance_ohm": 22.0, "load_capacitance_pf": 25.0},
    {"rail_v": 1.773, "series_resistance_ohm": 0.0, "load_capacitance_pf": 10.0},
    {"rail_v": 1.827, "series_resistance_ohm": 47.0, "load_capacitance_pf": 100.0},
    {"rail_v": 1.800, "series_resistance_ohm": 47.0, "load_capacitance_pf": 50.0},
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    crosschecks = [run_rc_spice_crosscheck(**case) for case in CROSSCHECK_CASES]
    all_pass = all(row["crosscheck_pass"] is True for row in crosschecks)
    payload = {
        "schema_version": "hardware_splicer.spi_derived_rc_spice_campaign.v1",
        "status": "passed_derived_rc_spice_campaign" if all_pass else "failed_derived_rc_spice_campaign",
        "campaign_pass": all_pass,
        "analytical_sweep": build_rc_sweep(),
        "crosschecks": crosschecks,
        "crosscheck_count": len(crosschecks),
        "evidence_class": "derived_surrogate_only",
        "vendor_model_campaign_credit_eligible": False,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
        "nonclaims": [
            "The RC model is a lumped development surrogate, not IBIS.",
            "ngspice agreement validates only the encoded RC network arithmetic.",
            "This campaign cannot earn manufacturer-model or physical-evidence credit.",
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"campaign_pass": all_pass, "crosscheck_count": len(crosschecks)}, sort_keys=True))
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
