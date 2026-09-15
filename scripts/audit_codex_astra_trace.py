#!/usr/bin/env python3
"""Audit a saved Codex/Astra JSONL trace without contacting Codex or any provider."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
sys.path[:] = [
    str(_REPO_ROOT / "src"),
    *[entry for entry in sys.path if Path(entry or os.curdir).resolve() != _SCRIPT_DIR],
]

from hardware_splicer.codex_exec_trace import (
    audit_codex_exec_trace,
    normalize_codex_exec_events,
    parse_codex_jsonl,
)
from hardware_splicer.codex_final_report import audit_codex_final_report
from hardware_splicer.codex_mission_progress import audit_codex_mission_progress
from hardware_splicer.codex_progress_provenance import audit_codex_progress_provenance
from hardware_splicer.external_mcp_trace_audit import snapshot_source_ids


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"expected a JSON object in {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize and audit a previously captured codex exec --json trace. "
            "This command performs no provider or MCP network I/O."
        )
    )
    parser.add_argument("--trace-file", required=True)
    parser.add_argument("--expected-project-id", required=True)
    parser.add_argument(
        "--snapshot-file",
        required=True,
        help=(
            "Exact product-visible frozen case snapshot used for evidence identity and "
            "minimum mission-progress/provenance comparison."
        ),
    )
    parser.add_argument("--model", default="gpt-6-astra")
    parser.add_argument("--out")
    args = parser.parse_args()

    trace_path = Path(args.trace_file).expanduser().resolve()
    snapshot_path = Path(args.snapshot_file).expanduser().resolve()
    events = parse_codex_jsonl(trace_path.read_text(encoding="utf-8"))
    snapshot = _load_json(snapshot_path)
    audit = audit_codex_exec_trace(
        events,
        model=args.model,
        expected_project_id=args.expected_project_id,
        known_source_ids=snapshot_source_ids(snapshot),
    )
    normalized = normalize_codex_exec_events(events, model=args.model)
    mission_progress = audit_codex_mission_progress(
        normalized,
        expected_project_id=args.expected_project_id,
        initial_snapshot=snapshot,
    )
    progress_provenance = audit_codex_progress_provenance(
        normalized,
        expected_project_id=args.expected_project_id,
        initial_snapshot=snapshot,
        mission_progress=mission_progress,
    )
    final_report = audit_codex_final_report(
        events,
        expected_project_id=args.expected_project_id,
        expected_final_revision=mission_progress.get("final_project_revision"),
        grounded_blockers=mission_progress.get("grounded_blocker_strings") or [],
    )
    audit["codex_mission_progress_audit"] = mission_progress
    audit["codex_mission_progress_contract_pass"] = mission_progress["contract_pass"]
    audit["codex_progress_provenance_audit"] = progress_provenance
    audit["codex_progress_provenance_contract_pass"] = progress_provenance[
        "contract_pass"
    ]
    audit["codex_final_report_audit"] = final_report
    audit["codex_final_report_contract_pass"] = final_report["contract_pass"]
    audit["codex_evaluation_ready_pass"] = bool(
        audit.get("codex_hard_truth_contract_pass")
        and mission_progress["contract_pass"]
        and progress_provenance["contract_pass"]
        and final_report["contract_pass"]
    )
    audit.update(
        {
            "trace_file": str(trace_path),
            "snapshot_file": str(snapshot_path),
            "offline_audit": True,
            "provider_network_io_performed": False,
            "mcp_network_io_performed": False,
            "correct_engineering_architecture_asserted": False,
            "physical_correctness": "UNPROVEN",
            "physical_authority_granted": False,
        }
    )
    rendered = json.dumps(audit, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.out:
        out = Path(args.out).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if audit.get("codex_evaluation_ready_pass") is True else 9


if __name__ == "__main__":
    raise SystemExit(main())
