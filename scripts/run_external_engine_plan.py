#!/usr/bin/env python3
"""Execute an HS-reviewed external engine task graph on a local trusted machine.

External CAD/EDA programs can execute code from supplied projects. Run only
with reviewed projects in an isolated local/container environment. This CLI
never flashes electronics, starts motors, or authorizes fabrication.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hardware_splicer.external_engine_orchestration import (  # noqa: E402
    EnginePlanError, preview_engine_plan, run_external_engine_plan,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="reviewed plan JSON")
    parser.add_argument("--workspace", type=Path, required=True,
                        help="source project root (trust boundary)")
    parser.add_argument("--out", type=Path, help="empty result directory")
    parser.add_argument("--execute", action="store_true",
                        help="explicitly execute installed third-party CAD/EDA programs")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not args.execute:
        preview = preview_engine_plan(plan)
        print(json.dumps(preview, indent=2))
        return
    if args.out is None:
        parser.error("--execute requires --out for source-bound evidence")
    report = run_external_engine_plan(
        plan, workspace=args.workspace, output_dir=args.out,
        confirm_execute=True, timeout_s=args.timeout,
    )
    print(json.dumps({
        "report": str(args.out / "ENGINE_ORCHESTRATION_REPORT.json"),
        "completed": report["completed"],
        "blocked": report["blocked"],
        "tasks": [{key: x.get(key) for key in ("id", "engine", "status")} for x in report["tasks"]],
        "physical_authority": False,
    }, indent=2))
    if report["blocked"]:
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except EnginePlanError as exc:
        raise SystemExit(f"External-engine plan rejected: {exc}") from exc
