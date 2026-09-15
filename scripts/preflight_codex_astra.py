#!/usr/bin/env python3
"""Preflight and print a zero-execution Codex/Astra launch plan for Hardware-Splicer."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Direct execution from scripts/ would otherwise import legacy scripts/hardware_splicer.py
# instead of the installed package. Keep this identical in spirit to the hardened proof runner.
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
sys.path[:] = [
    str(_REPO_ROOT / "src"),
    *[
        entry
        for entry in sys.path
        if Path(entry or os.curdir).resolve() != _SCRIPT_DIR
    ],
]

from hardware_splicer.codex_astra_case import frozen_case_instructions
from hardware_splicer.codex_astra_preflight import (
    ASTRA_MODEL,
    build_codex_exec_argv,
    run_zero_inference_preflight,
    shell_quote_argv,
)
from hardware_splicer.codex_astra_runtime import BLOCKED_PROVIDER_ENV, blocked_provider_env_names


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _inject_frozen_developer_instructions(argv: list[str]) -> list[str]:
    if not argv:
        raise ValueError("Codex argv must not be empty")
    override = "developer_instructions=" + json.dumps(frozen_case_instructions())
    return [argv[0], "-c", override, *argv[1:]]


def _safe_shell_display(argv: list[str], mission_file: Path, trace_file: Path) -> str:
    # `codex exec` can honor CODEX_API_KEY from its environment. The display must
    # therefore be safe even when copied manually rather than executed by our runner.
    unsets = " ".join(f"-u {name}" for name in BLOCKED_PROVIDER_ENV)
    return (
        f"env {unsets} {shell_quote_argv(argv)} < {shell_quote_argv([str(mission_file)])} "
        f"> {shell_quote_argv([str(trace_file)])}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check Codex/Astra/HS clean-room prerequisites and optionally emit the exact "
            "future codex exec command. This script never launches Codex inference."
        )
    )
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--hs-repo-root", required=True)
    parser.add_argument("--codex-command", default="codex")
    parser.add_argument("--mcp-command", default="hs-backend-mcp")
    parser.add_argument("--mcp-arg", action="append", default=[])
    parser.add_argument("--mission-file")
    parser.add_argument("--report-file")
    parser.add_argument(
        "--emit-launch-plan",
        action="store_true",
        help="Include the exact future codex exec argv/shell rendering without executing it.",
    )
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    parent_credential_names = blocked_provider_env_names(dict(os.environ))
    report = run_zero_inference_preflight(
        workspace=workspace,
        hs_repo_root=args.hs_repo_root,
        codex_command=args.codex_command,
        mcp_command=args.mcp_command,
    )
    payload = report.as_dict()
    payload.update(
        {
            "model_target": ASTRA_MODEL,
            "frozen_developer_instructions_applied_to_launch_plan": True,
            "parent_provider_credentials_present": list(parent_credential_names),
            "launch_plan_unsets_provider_credentials": True,
            "live_execution_performed": False,
            "codex_allowance_consumed_by_this_script": False,
        }
    )

    if args.emit_launch_plan:
        if not args.mission_file:
            raise SystemExit("--emit-launch-plan requires --mission-file")
        mission_file = Path(args.mission_file).expanduser().resolve()
        if mission_file.parent != workspace:
            raise SystemExit("mission file must live directly inside --workspace")
        if not mission_file.is_file():
            raise SystemExit(f"mission file does not exist: {mission_file}")
        trace_file = workspace / "CODEX_ASTRA_TRACE.jsonl"
        last_message_file = workspace / "CODEX_ASTRA_LAST_MESSAGE.txt"
        argv = build_codex_exec_argv(
            workspace=workspace,
            hs_repo_root=args.hs_repo_root,
            mcp_command=args.mcp_command,
            mcp_args=args.mcp_arg,
            prompt_file=mission_file,
            trace_file=trace_file,
            last_message_file=last_message_file,
            codex_command=args.codex_command,
        )
        argv = _inject_frozen_developer_instructions(argv)
        payload["launch_plan"] = {
            "argv": argv,
            "environment_unsets": list(BLOCKED_PROVIDER_ENV),
            "shell_display": _safe_shell_display(argv, mission_file, trace_file),
            "stdin_file": str(mission_file),
            "stdout_trace_file": str(trace_file),
            "last_message_file": str(last_message_file),
            "developer_instructions_source": "frozen external MCP proof protocol",
            "requires_separate_manual_execution": True,
            "inference_performed": False,
        }

    if args.report_file:
        _write_json(Path(args.report_file).expanduser().resolve(), payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report.pass_ else 2


if __name__ == "__main__":
    raise SystemExit(main())
