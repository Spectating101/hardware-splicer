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
from hardware_splicer.github_signal_worker_registry import (
    TASK_CAPABILITIES, configure_worker, discover_github_self_hosted, read_registry,
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
    workers=sub.add_parser("workers", help="Inspect or explicitly configure approved worker pool")
    worksub=workers.add_subparsers(dest="worker_action", required=True)
    worksub.add_parser("show", help="Read the currently approved logical execution pool")
    worksub.add_parser("discover", help="Read-only GitHub self-hosted runner inventory; no enrollment")
    manage=worksub.add_parser("configure", help="Approve/pause and bound GitHub Actions worker")
    manage.add_argument("--approve", action="store_true",
                        help="Required explicit authorization to change worker pool")
    manage.add_argument("--state", choices=["approved","paused"], default="approved")
    manage.add_argument("--max-inflight", type=int, default=2)
    manage.add_argument("--allow-task", choices=sorted(TASK_CAPABILITIES), action="append",
                        dest="allow_tasks")
    args=p.parse_args()
    client=GithubCLI() if args.action != "workers" or args.worker_action == "discover" else None
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
        elif args.action=="workers":
            if args.worker_action=="show":
                result=read_registry(args.ledger)
            elif args.worker_action=="discover":
                result=discover_github_self_hosted(client)
            elif args.worker_action=="configure":
                result=configure_worker(
                    args.ledger, approve=args.approve, state=args.state,
                    max_inflight=args.max_inflight, allowed_tasks=args.allow_tasks,
                )
            else:
                raise WorkerStateError("unsupported worker action")
        else:
            raise WorkerStateError("unsupported action")
    except (WorkerStateError, OSError, ValueError, KeyError) as exc:
        print(json.dumps({"ok":False,"action":args.action,"error":str(exc)},indent=2))
        return 2
    print(json.dumps({"ok":True,"job":result},indent=2,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
