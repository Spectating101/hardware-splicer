#!/usr/bin/env python3
"""Audit captured Hardware Splicer model-first outputs for semantic authority leakage."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from hardware_splicer.model_first_truth_audit import audit_model_first_truth


def _load(path: str | None) -> Dict[str, Any] | None:
    if not path:
        return None
    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"audit input does not exist: {source}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"audit input is not valid JSON: {source}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"audit input must contain one JSON object: {source}")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit effective model-first project/circuit/salvage/topology/impact outputs "
            "for legacy semantic authority, false physical identity, and open authority."
        )
    )
    parser.add_argument("--project-plan", help="JSON project/engineering plan")
    parser.add_argument("--circuit-candidate", help="JSON circuit synthesis candidate")
    parser.add_argument("--salvage-package", help="JSON salvage/splice package")
    parser.add_argument("--robot-topology", help="JSON robot topology")
    parser.add_argument("--change-impact", help="JSON change-impact graph")
    parser.add_argument("--out", help="Optional path for the JSON audit report")
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the report to stdout.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    inputs = {
        "project_plan": _load(args.project_plan),
        "circuit_candidate": _load(args.circuit_candidate),
        "salvage_package": _load(args.salvage_package),
        "robot_topology": _load(args.robot_topology),
        "change_impact": _load(args.change_impact),
    }
    if not any(value is not None for value in inputs.values()):
        raise SystemExit("provide at least one model-first output JSON to audit")

    report = audit_model_first_truth(**inputs)
    rendered = json.dumps(
        report,
        indent=2 if args.pretty or args.out else None,
        sort_keys=True,
    )
    if args.out:
        destination = Path(args.out)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report.get("status") == "pass" else 2


if __name__ == "__main__":
    sys.exit(main())
