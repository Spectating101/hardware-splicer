#!/usr/bin/env python3
"""Audit a saved Codex/Astra JSONL trace without contacting Codex or any provider."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from hardware_splicer.codex_exec_trace import (
    audit_codex_exec_trace,
    parse_codex_jsonl,
)
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
        help="Exact product-visible frozen case snapshot used for known source identities.",
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
    audit.update(
        {
            "trace_file": str(trace_path),
            "snapshot_file": str(snapshot_path),
            "offline_audit": True,
            "provider_network_io_performed": False,
            "mcp_network_io_performed": False,
        }
    )
    rendered = json.dumps(audit, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.out:
        out = Path(args.out).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if audit.get("codex_hard_truth_contract_pass") is True else 9


if __name__ == "__main__":
    raise SystemExit(main())
