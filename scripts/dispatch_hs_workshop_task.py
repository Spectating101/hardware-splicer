#!/usr/bin/env python3
"""HS controller for approved remote GitHub-source-native engineering tasks.

Stages: submit --execute, status, collect. No agent shells/devices/motors.
Default submit is a dry-run. Correlation and hash checks prevent attributing
someone else's remote workflow to HS.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hardware_splicer.github_signal_remote_dispatch import (
    GithubCLI, WorkerStateError, collect, status, submit,
)


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ledger", type=Path, required=True)
    sub=p.add_subparsers(dest="action", required=True)
    send=sub.add_parser("submit", help="Plan or dispatch one approved engineering job")
    send.add_argument("--objective", required=True)
    send.add_argument("--request-id")
    send.add_argument("--execute", action="store_true",
                      help="Explicit authorization to dispatch a GitHub Actions job")
    send.add_argument("--workspace", type=Path,
                      default=Path(__file__).resolve().parents[1])
    check=sub.add_parser("status", help="Resolve a remote job by correlated request ID")
    check.add_argument("--request-id", required=True)
    receive=sub.add_parser("collect", help="Fetch and verify the one approved remote artifact")
    receive.add_argument("--request-id", required=True)
    args=p.parse_args()
    client=GithubCLI()
    try:
        if args.action=="submit":
            result=submit(
                args.objective, ledger=args.ledger,
                workspace=args.workspace, client=client,
                request_id=args.request_id, execute=args.execute,
            )
        elif args.action=="status":
            result=status(ledger=args.ledger, request_id=args.request_id, client=client)
        elif args.action=="collect":
            result=collect(ledger=args.ledger, request_id=args.request_id, client=client)
        else:
            raise WorkerStateError("unsupported action")
    except (WorkerStateError, OSError, ValueError, KeyError) as exc:
        print(json.dumps({"ok":False,"action":args.action,"error":str(exc)},indent=2))
        return 2
    print(json.dumps({"ok":True,"job":result},indent=2,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
