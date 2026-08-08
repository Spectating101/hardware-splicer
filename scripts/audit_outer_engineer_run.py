#!/usr/bin/env python3
"""Run the combined Hardware Splicer outer-engineer truth audit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from hardware_splicer.outer_engineer_audit import audit_outer_engineer_run


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


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description=(
            "Audit model-first Hardware Splicer outputs for semantic-authority leakage "
            "and downstream physical-identity laundering."
        )
    )
    result.add_argument("--project-plan")
    result.add_argument("--circuit-candidate")
    result.add_argument("--salvage-package")
    result.add_argument("--robot-topology")
    result.add_argument("--change-impact")
    result.add_argument("--out")
    result.add_argument("--pretty", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    inputs = {
        "project_plan": _load(args.project_plan),
        "circuit_candidate": _load(args.circuit_candidate),
        "salvage_package": _load(args.salvage_package),
        "robot_topology": _load(args.robot_topology),
        "change_impact": _load(args.change_impact),
    }
    if not any(value is not None for value in inputs.values()):
        raise SystemExit("provide at least one captured Hardware Splicer output JSON")

    report = audit_outer_engineer_run(**inputs)
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
    if report.get("status") == "blocked":
        return 2
    if report.get("status") == "review":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
