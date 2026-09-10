#!/usr/bin/env python3
"""Run exactly one prepared Codex/Astra HS case with explicit allowance acknowledgement."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
sys.path[:] = [
    str(_REPO_ROOT),
    *[entry for entry in sys.path if Path(entry or os.curdir).resolve() != _SCRIPT_DIR],
]

from hardware_splicer.codex_astra_preflight import run_zero_inference_preflight
from hardware_splicer.codex_astra_runtime import (
    CODEX_ALLOWANCE_CONFIRMATION,
    build_single_case_runtime_argv,
    claim_live_execution,
    runtime_plan,
    sanitized_runtime_environment,
    validate_execution_acknowledgement,
    validate_runtime_manifest,
)
from hardware_splicer.codex_exec_trace import (
    audit_codex_exec_trace,
    normalize_codex_exec_events,
    parse_codex_jsonl,
)
from hardware_splicer.codex_final_report import (
    attach_output_schema_arg,
    audit_codex_final_report,
    final_report_schema_sha256,
    write_final_report_schema,
)
from hardware_splicer.codex_mission_progress import audit_codex_mission_progress
from hardware_splicer.codex_progress_provenance import audit_codex_progress_provenance
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
    output_schema_path = context.observer_dir / "CODEX_ASTRA_FINAL_REPORT_SCHEMA.json"
    try:
        write_final_report_schema(output_schema_path)
        argv = build_single_case_runtime_argv(
            context,
            codex_command=preflight.codex_path,
            mcp_command=preflight.mcp_command,
        )
        argv = attach_output_schema_arg(argv, output_schema_path)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"cannot prepare structured Astra output contract: {exc}") from exc

    plan = runtime_plan(context, argv=argv, source_env=dict(os.environ))
    plan["preflight"] = preflight.as_dict()
    plan["timeout_seconds"] = args.timeout_seconds
    plan["execute_requested"] = bool(args.execute)
    plan["output_schema_file"] = str(output_schema_path)
    plan["output_schema_sha256"] = final_report_schema_sha256()
    plan["structured_final_report_required"] = True
    plan["operation_to_state_provenance_required"] = True

    if not args.execute:
        plan["required_live_acknowledgement"] = CODEX_ALLOWANCE_CONFIRMATION
        print(json.dumps(plan, indent=2, ensure_ascii=False, sort_keys=True))
        return 0

    try:
        attempt_path = claim_live_execution(context)
    except ValueError as exc:
        payload = {
            "schema_version": "hardware_splicer.codex_astra_run_refusal.v1",
            "reason": "live execution attempt already claimed",
            "message": str(exc),
            "execution_performed": False,
            "api_fallback": False,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 3

    plan["live_execution_claim"] = str(attempt_path)
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
            "schema_version": "hardware_splicer.codex_astra_run_result.v4",
            "status": "timeout",
            "timeout_seconds": args.timeout_seconds,
            "live_execution_claim": str(attempt_path),
            "trace_file": str(trace_path),
            "stderr_file": str(stderr_path),
            "output_schema_file": str(output_schema_path),
            "api_fallback": False,
            "physical_authority_granted": False,
        }
        _write_json(result_path, result)
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return 124
    except OSError as exc:
        result = {
            "schema_version": "hardware_splicer.codex_astra_run_result.v4",
            "status": "launch_error",
            "error": f"{type(exc).__name__}: {exc}",
            "live_execution_claim": str(attempt_path),
            "trace_file": str(trace_path),
            "stderr_file": str(stderr_path),
            "output_schema_file": str(output_schema_path),
            "api_fallback": False,
            "physical_authority_granted": False,
        }
        _write_json(result_path, result)
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return 126

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
        normalized = normalize_codex_exec_events(events, model="gpt-6-astra")
        mission_progress = audit_codex_mission_progress(
            normalized,
            expected_project_id=context.experiment_project_id,
            initial_snapshot=snapshot,
        )
        progress_provenance = audit_codex_progress_provenance(
            normalized,
            expected_project_id=context.experiment_project_id,
            initial_snapshot=snapshot,
            mission_progress=mission_progress,
        )
        final_report = audit_codex_final_report(
            events,
            expected_project_id=context.experiment_project_id,
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
        _write_json(audit_path, audit)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        audit_error = f"{type(exc).__name__}: {exc}"

    passed = bool(
        completed.returncode == 0
        and audit is not None
        and audit.get("codex_evaluation_ready_pass") is True
    )
    result = {
        "schema_version": "hardware_splicer.codex_astra_run_result.v4",
        "status": "passed" if passed else "failed",
        "codex_exit_code": completed.returncode,
        "codex_hard_truth_contract_pass": (
            audit.get("codex_hard_truth_contract_pass") if audit else False
        ),
        "codex_mission_progress_contract_pass": (
            audit.get("codex_mission_progress_contract_pass") if audit else False
        ),
        "codex_progress_provenance_contract_pass": (
            audit.get("codex_progress_provenance_contract_pass") if audit else False
        ),
        "codex_final_report_contract_pass": (
            audit.get("codex_final_report_contract_pass") if audit else False
        ),
        "codex_evaluation_ready_pass": (
            audit.get("codex_evaluation_ready_pass") if audit else False
        ),
        "audit_error": audit_error,
        "live_execution_claim": str(attempt_path),
        "trace_file": str(trace_path),
        "stderr_file": str(stderr_path),
        "audit_file": str(audit_path) if audit is not None else None,
        "output_schema_file": str(output_schema_path),
        "output_schema_sha256": final_report_schema_sha256(),
        "codex_usage": audit.get("codex_usage") if audit else None,
        "api_fallback": False,
        "provider_credentials_forwarded_to_runtime": False,
        "single_case_only": True,
        "one_live_attempt_per_prepared_case": True,
        "correct_engineering_architecture_asserted": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
    }
    _write_json(result_path, result)
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if passed else 9


if __name__ == "__main__":
    raise SystemExit(main())
