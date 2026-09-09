#!/usr/bin/env python3
"""Run exactly one prepared Codex/Astra HS case with explicit allowance acknowledgement."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from hardware_splicer.codex_astra_preflight import run_zero_inference_preflight
from hardware_splicer.codex_astra_runtime import (
    CODEX_ALLOWANCE_CONFIRMATION,
    build_single_case_runtime_argv,
    runtime_plan,
    sanitized_runtime_environment,
    validate_execution_acknowledgement,
    validate_runtime_manifest,
)
from hardware_splicer.codex_exec_trace import (
    audit_codex_exec_trace,
    parse_codex_jsonl,
)
from hardware_splicer.external_mcp_trace_audit import snapshot_source_ids


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object in {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Dry-run by default. With --execute plus an exact acknowledgement, run one "
            "prepared frozen case through ChatGPT-authenticated Codex/Astra, persist JSONL, "
            "and audit it offline. Never falls back to an API key."
        )
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--codex-command", default="codex")
    parser.add_argument("--mcp-command", default="hs-backend-mcp")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-codex-allowance")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args()

    if args.timeout_seconds < 30 or args.timeout_seconds > 1800:
        raise SystemExit("--timeout-seconds must be between 30 and 1800")
    try:
        validate_execution_acknowledgement(
            execute=args.execute,
            confirmation=args.confirm_codex_allowance,
        )
        context = validate_runtime_manifest(args.manifest)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    preflight = run_zero_inference_preflight(
        workspace=context.workspace,
        hs_repo_root=context.hs_repo_root,
        codex_command=args.codex_command,
        mcp_command=args.mcp_command,
    )
    if not preflight.pass_:
        payload = {
            "schema_version": "hardware_splicer.codex_astra_run_refusal.v1",
            "reason": "zero-inference preflight failed",
            "preflight": preflight.as_dict(),
            "execution_performed": False,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 2

    assert preflight.codex_path is not None
    assert preflight.mcp_command is not None
    argv = build_single_case_runtime_argv(
        context,
        codex_command=preflight.codex_path,
        mcp_command=preflight.mcp_command,
    )
    plan = runtime_plan(context, argv=argv, source_env=dict(__import__("os").environ))
    plan["preflight"] = preflight.as_dict()
    plan["timeout_seconds"] = args.timeout_seconds
    plan["execute_requested"] = bool(args.execute)

    if not args.execute:
        plan["required_live_acknowledgement"] = CODEX_ALLOWANCE_CONFIRMATION
        print(json.dumps(plan, indent=2, ensure_ascii=False, sort_keys=True))
        return 0

    runtime_plan_path = context.observer_dir / "CODEX_ASTRA_RUNTIME_PLAN.json"
    _write_json(runtime_plan_path, {**plan, "execution_performed": True})
    trace_path = context.observer_dir / "CODEX_ASTRA_TRACE.jsonl"
    stderr_path = context.observer_dir / "CODEX_ASTRA_STDERR.log"
    result_path = context.observer_dir / "CODEX_ASTRA_RUN_RESULT.json"
    audit_path = context.observer_dir / "CODEX_ASTRA_AUDIT.json"
    mission_text = context.mission_file.read_text(encoding="utf-8")
    runtime_env = sanitized_runtime_environment()

    try:
        with trace_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
            "w", encoding="utf-8"
        ) as stderr_handle:
            completed = subprocess.run(
                argv,
                input=mission_text,
                text=True,
                stdout=stdout_handle,
                stderr=stderr_handle,
                cwd=context.workspace,
                env=runtime_env,
                check=False,
                timeout=args.timeout_seconds,
            )
    except subprocess.TimeoutExpired:
        result = {
            "schema_version": "hardware_splicer.codex_astra_run_result.v1",
            "status": "timeout",
            "timeout_seconds": args.timeout_seconds,
            "trace_file": str(trace_path),
            "stderr_file": str(stderr_path),
            "api_fallback": False,
            "physical_authority_granted": False,
        }
        _write_json(result_path, result)
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return 124

    audit: dict | None = None
    audit_error: str | None = None
    try:
        events = parse_codex_jsonl(trace_path.read_text(encoding="utf-8"))
        snapshot = _load_json(context.snapshot_file)
        audit = audit_codex_exec_trace(
            events,
            model="gpt-6-astra",
            expected_project_id=context.experiment_project_id,
            known_source_ids=snapshot_source_ids(snapshot),
        )
        _write_json(audit_path, audit)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        audit_error = f"{type(exc).__name__}: {exc}"

    passed = bool(
        completed.returncode == 0
        and audit is not None
        and audit.get("codex_hard_truth_contract_pass") is True
    )
    result = {
        "schema_version": "hardware_splicer.codex_astra_run_result.v1",
        "status": "passed" if passed else "failed",
        "codex_exit_code": completed.returncode,
        "codex_hard_truth_contract_pass": (
            audit.get("codex_hard_truth_contract_pass") if audit else False
        ),
        "audit_error": audit_error,
        "trace_file": str(trace_path),
        "stderr_file": str(stderr_path),
        "audit_file": str(audit_path) if audit is not None else None,
        "codex_usage": audit.get("codex_usage") if audit else None,
        "api_fallback": False,
        "provider_credentials_forwarded_to_runtime": False,
        "single_case_only": True,
        "physical_authority_granted": False,
    }
    _write_json(result_path, result)
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if passed else 9


if __name__ == "__main__":
    raise SystemExit(main())
