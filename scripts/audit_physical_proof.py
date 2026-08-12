#!/usr/bin/env python3
"""Audit the evidence ceiling of a Hardware Splicer bench session.

Exit 0 means the persisted bench evidence is internally defensible at its reported claim
ceiling. Exit 2 means the audit found blocking evidence/authority inconsistencies. The
script never authorizes fabrication, power, motion, or release.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from hardware_splicer.physical_proof_audit import audit_physical_proof_build


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build_dir", help="Hardware Splicer build directory")
    parser.add_argument(
        "--capture",
        help="Optional bench_topology_capture JSON used to distinguish real/simulated/independent proof",
    )
    parser.add_argument(
        "--require-independent",
        action="store_true",
        help="Fail unless explicit independent-operator attestation is present and bench evidence is complete",
    )
    parser.add_argument(
        "--out",
        help="Optional path for PHYSICAL_PROOF_AUDIT.json (defaults inside build_dir)",
    )
    args = parser.parse_args()

    report = audit_physical_proof_build(args.build_dir, capture_path=args.capture)
    out_path = Path(args.out).resolve() if args.out else Path(args.build_dir).resolve() / "PHYSICAL_PROOF_AUDIT.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps({
        "status": report["status"],
        "claim_ceiling": report["claim_ceiling"],
        "bench_evidence_complete": report["bench_evidence_complete"],
        "independent_operator_proof": report["independent_operator_proof"],
        "blocking_finding_count": report["blocking_finding_count"],
        "report_path": str(out_path),
    }, indent=2))

    if report["status"] != "pass":
        return 2
    if args.require_independent and not report["independent_operator_proof"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
