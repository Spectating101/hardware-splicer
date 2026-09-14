#!/usr/bin/env python3
"""Validate one exact recognized member from a captured manufacturer model payload."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from hardware_splicer.captured_model_materialization import extract_bound_model_member
from hardware_splicer.vendor_model_validation import (
    validate_ibis_model_bytes,
    validate_verilog_model_bytes,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--capture-manifest", type=Path, required=True)
    parser.add_argument("--member", required=True)
    parser.add_argument("--tool", help="optional parser/compiler executable override")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.capture_manifest.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise SystemExit("capture manifest must be a JSON object")
    outer = args.payload.read_bytes()
    model_bytes, materialization = extract_bound_model_member(
        outer, manifest, member_path=args.member
    )

    kind = materialization["model_kind"]
    if kind == "IBIS":
        kwargs = {"parser_executable": args.tool} if args.tool else {}
        validation = validate_ibis_model_bytes(
            model_bytes,
            manifest,
            member_path=args.member,
            timeout_s=args.timeout,
            **kwargs,
        )
    elif kind == "Verilog":
        kwargs = {"compiler_executable": args.tool} if args.tool else {}
        validation = validate_verilog_model_bytes(
            model_bytes,
            manifest,
            member_path=args.member,
            timeout_s=args.timeout,
            **kwargs,
        )
    else:
        raise SystemExit(f"unsupported recognized model kind: {kind}")

    result = {
        "schema_version": "hardware_splicer.captured_vendor_model_validation.v1",
        "materialization": materialization,
        "validation": validation,
        "modeled_evidence_only": True,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")

    status = validation.get("status")
    if status == "passed_syntax_validation":
        return 0
    if status in {"tool_unavailable", "blocked_unbound_include_dependencies"}:
        return 3
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
