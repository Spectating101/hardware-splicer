#!/usr/bin/env python3
"""Opt-in Optiplex KiCad ERC worker: identity/enroll/heartbeat/run/verify/revoke.

All execution is explicitly requested, read-only, and limited to the fixed HS
schematic. It is not a GitHub Actions self-hosted runner or device controller.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hardware_splicer.local_kicad_worker import (
    WorkerError, create_identity, enroll, heartbeat, nodes_status, revoke, run_erc, verify_erc, verify_bundle,
)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    p = parser.add_subparsers(dest="action", required=True)
    init = p.add_parser("identity", help="Create a new private local Ed25519 identity")
    init.add_argument("--key-dir", type=Path, required=True)
    for name in ("enroll", "heartbeat", "run", "verify", "revoke", "status"):
        sub = p.add_parser(name)
        sub.add_argument("--ledger", type=Path, required=True)
        if name in ("heartbeat", "run"):
            sub.add_argument("--key-dir", type=Path, required=True)
        if name == "enroll":
            sub.add_argument("--public-key", type=Path, required=True)
        if name in ("enroll", "revoke"):
            sub.add_argument("--approve", action="store_true")
        if name == "revoke":
            sub.add_argument("--worker-id", required=True)
        if name == "run":
            sub.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[1])
            sub.add_argument("--request-id")
            sub.add_argument("--execute", action="store_true")
        if name == "verify":
            sub.add_argument("--request-id", required=True)
            sub.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[1])
    bundle = p.add_parser("verify-bundle", help="Verify exported public signature and ERC report")
    bundle.add_argument("--bundle", type=Path, required=True)
    bundle.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[1])
    a = parser.parse_args()
    try:
        if a.action == "identity":
            result = create_identity(a.key_dir)
        elif a.action == "enroll":
            result = enroll(a.ledger, a.public_key, approve=a.approve)
        elif a.action == "heartbeat":
            result = heartbeat(a.ledger, a.key_dir)
        elif a.action == "verify-bundle":
            result = verify_bundle(a.bundle, a.workspace)
        elif a.action == "status":
            result = nodes_status(a.ledger)
        elif a.action == "run":
            result = run_erc(a.ledger, a.key_dir, a.workspace,
                             execute=a.execute, request_id=a.request_id)
        elif a.action == "verify":
            result = verify_erc(a.ledger, a.workspace, a.request_id)
        else:
            result = revoke(a.ledger, a.worker_id, approve=a.approve)
        print(json.dumps({"ok": True, "result": result}, indent=2, sort_keys=True))
        return 0
    except (WorkerError, OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "action": a.action, "error": str(exc)}, indent=2))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
