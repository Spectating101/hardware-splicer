"""Recompute explicitly hypothetical acquisition economics, never purchase."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hardware_splicer.salvage_purchase_screen import screen, sensitivity


DEFAULT = Path(__file__).resolve().parents[1] / "docs/research/tw_salvage_sourcing_scenarios_2026-10-19.json"


def evaluate(path: Path) -> dict:
    data = json.loads(path.read_text())
    if data.get("schema_version") != "hardware_splicer.salvage_sourcing_research.v1":
        raise ValueError("unsupported research schema")
    return {
        "schema_version": "hardware_splicer.salvage_purchase_screen_report.v1",
        "source": path.name,
        "status": "SCENARIOS_ONLY_NO_PURCHASE_AUTHORITY",
        "evaluations": [{
            "id": item["id"],
            "modeled_unit_economics": screen(item),
            "downside_sensitivity": sensitivity(item),
            "failure_mode_gate": item["hard_stop"],
            "resale_assumption": item["sale_assumption_note"],
            "source_confidence": item["source_confidence"],
            "source_urls": item["source_urls"],
            "comparable_urls": item["comparable_urls"],
        } for item in data["opportunities"]],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    data = json.dumps(evaluate(args.input), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(data, encoding="utf-8")
    else:
        print(data)


if __name__ == "__main__":
    main()
