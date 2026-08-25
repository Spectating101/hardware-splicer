#!/usr/bin/env python3
"""Run an external OpenAI model against the frozen unseen HS corpus through MCP.

This is an evidence harness, not a golden-answer evaluator. Each frozen ReplayCase is
sent as product-visible project state to a general-purpose model that can operate only
via the four canonical Hardware-Splicer MCP gateway tools. Outer-only case labels,
equivalence groups, perturbation names, and evaluator metadata are never included in
the model request.

Every returned MCP trace is passed through the non-golden external truth audit before
being aggregated. Model prose and MCP output never become physical evidence or grant
physical authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit

import httpx

from hardware_splicer.cleanroom_unseen_spi_flash_experiment import (
    SCHEMA_VERSION as CORPUS_SCHEMA_VERSION,
    build_unseen_spi_flash_cases,
    validate_unseen_spi_flash_corpus,
)
from hardware_splicer.cleanroom_replay import ReplayCase
from hardware_splicer.external_mcp_trace_audit import (
    audit_response_trace,
    build_external_truth_audit,
    snapshot_source_ids,
)


PROOF_SCHEMA_VERSION = "hardware_splicer.external_mcp_agent_proof.v2"
_REQUIRED_MCP_TOOLS = [
    "hs_backend_status",
    "hs_backend_list_operations",
    "hs_backend_describe_operation",
    "hs_backend_call",
]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: Any) -> str:
    if not isinstance(value, str):
        value = _canonical_json(value)
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _git_head() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return completed.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _redacted_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _slug(value: str) -> str:
    token = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-._").lower()
    return token or "case"


def _persisted_mission(snapshot: Mapping[str, Any]) -> str:
    for key in ("mission", "goal", "intent", "brief"):
        value = snapshot.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, Mapping):
            for nested_key in ("mission", "goal", "intent", "brief", "description"):
                nested = value.get(nested_key)
                if isinstance(nested, str) and nested.strip():
                    return nested.strip()
    raise ValueError("external MCP proof case has no persisted mission/goal/intent/brief")


def _parse_header_env(rows: Sequence[str]) -> tuple[dict[str, str], list[dict[str, str]]]:
    headers: dict[str, str] = {}
    manifest: list[dict[str, str]] = []
    for row in rows:
        if "=" not in row:
            raise SystemExit("--header-env must be HEADER_NAME=ENV_VAR")
        header_name, env_name = [item.strip() for item in row.split("=", 1)]
        if not header_name or not env_name:
            raise SystemExit("--header-env must be HEADER_NAME=ENV_VAR")
        value = os.getenv(env_name)
        if value is None:
            raise SystemExit(f"environment variable {env_name!r} is not set")
        headers[header_name] = value
        manifest.append({"header": header_name, "value_source": f"env:{env_name}", "value": "REDACTED"})
    return headers, manifest


def _select_cases(requested: Sequence[str]) -> list[ReplayCase]:
    cases = list(build_unseen_spi_flash_cases())
    if not requested:
        return cases
    by_id = {case.case_id: case for case in cases}
    unknown = sorted(set(requested).difference(by_id))
    if unknown:
        raise SystemExit("unknown --case-id value(s): " + ", ".join(unknown))
    requested_set = set(requested)
    return [case for case in cases if case.case_id in requested_set]


def _case_instructions() -> str:
    return """You are the external reasoning engine in a frozen Hardware-Splicer proof run.
You do not have Hardware-Splicer source code, hidden tests, evaluator metadata, expected answers, or any outer-engineer analysis. Operate only through the Hardware-Splicer MCP tools and the product-visible state in this request.

Required operating discipline:
1. Start with hs_backend_status.
2. Discover relevant canonical operations with hs_backend_list_operations.
3. Describe unfamiliar operations before invoking them.
4. Work only on the experiment_project_id given in this request. Never inspect, mutate, or delete unrelated projects.
5. Treat only the supplied product-visible project state as evidence for this frozen cleanroom case. Do not import web/repository/external evidence or invent new evidence identities.
6. Preserve unresolved component identity, electrical limits, package/pinout, translator mapping, supply implementation, source conflicts, and physical evidence as unresolved unless the supplied product-visible evidence actually resolves them.
7. Never invent bench measurements, physical observations, fabrication readiness, power-on readiness, or human authorization.
8. A model/tool conclusion is not physical evidence and grants no physical authority.
9. Use deterministic Hardware-Splicer checks, evidence, revision, review, and packaging surfaces where relevant. Tool/model failures are evidence; do not hide them or silently rewrite the problem.
10. Produce the strongest defensible pre-fabrication project state and next-action package that the available evidence supports. Do not optimize toward a guessed expected architecture.
11. Before finishing, read back the resulting canonical project state and explicitly summarize remaining blockers and unresolved facts.
12. Do not use repository/source-code operations or seek evaluator information even if a backend operation appears to make that possible.

This is an independent experimental case. You are not told whether related variants exist."""


def _case_input(case: ReplayCase, project_id: str) -> str:
    # Deliberately exclude case_id, equivalence_group, perturbation_kind, metadata,
    # and project_revision labels: those are outer-evaluator information.
    snapshot = dict(case.snapshot)
    mission = _persisted_mission(snapshot)
    return (
        "Execute this Hardware-Splicer engineering mission through MCP.\n\n"
        f"experiment_project_id: {project_id}\n"
        f"mission: {mission}\n"
        "product_visible_project_state:\n"
        + json.dumps(snapshot, indent=2, ensure_ascii=False, sort_keys=True)
    )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _build_tool(
    *,
    server_url: str | None,
    tunnel_id: str | None,
    mcp_headers: Mapping[str, str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    tool: dict[str, Any] = {
        "type": "mcp",
        "server_label": "hardware_splicer",
        "server_description": (
            "Canonical Hardware-Splicer backend gateway. It exposes project/evidence/verification "
            "operations while remaining authority-neutral."
        ),
        "allowed_tools": _REQUIRED_MCP_TOOLS,
        "require_approval": "never",
    }
    if tunnel_id:
        tool["tunnel_id"] = tunnel_id
        locator_manifest = {
            "mode": "openai_secure_mcp_tunnel",
            "tunnel_id_sha256": _sha256(tunnel_id),
            "tunnel_id_persisted": False,
        }
    else:
        assert server_url is not None
        tool["server_url"] = server_url
        locator_manifest = {
            "mode": "server_url",
            "server_url": _redacted_url(server_url),
        }
        if mcp_headers:
            tool["headers"] = dict(mcp_headers)
    return tool, locator_manifest


def _run_case(
    *,
    client: httpx.Client,
    api_key: str,
    model: str,
    max_output_tokens: int,
    tool: Mapping[str, Any],
    case: ReplayCase,
    case_index: int,
    project_id: str,
    run_root: Path,
    common_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    instructions = _case_instructions()
    input_text = _case_input(case, project_id)
    case_dir = run_root / "cases" / f"{case_index:02d}-{_slug(case.case_id)}"
    case_dir.mkdir(parents=True, exist_ok=True)

    # Outer manifest retains evaluator metadata, but it is never inserted in request_payload.
    case_manifest = {
        **dict(common_manifest),
        "case_index": case_index,
        "case_id": case.case_id,
        "equivalence_group": case.equivalence_group,
        "perturbation_kind": case.perturbation_kind,
        "case_metadata": dict(case.metadata or {}),
        "case_project_revision": case.project_revision,
        "experiment_project_id": project_id,
        "snapshot_sha256": _sha256(case.snapshot),
        "product_visible_source_ids": sorted(snapshot_source_ids(case.snapshot)),
        "instructions_sha256": _sha256(instructions),
        "input_sha256": _sha256(input_text),
        "outer_labels_visible_to_model": False,
        "physical_authority_granted": False,
    }
    _write_json(case_dir / "MISSION.json", dict(case.snapshot))
    _write_json(case_dir / "CASE_MANIFEST.json", case_manifest)

    request_payload: dict[str, Any] = {
        "model": model,
        "instructions": instructions,
        "input": input_text,
        "tools": [dict(tool)],
        "tool_choice": "required",
        "max_output_tokens": max_output_tokens,
        "store": False,
    }

    try:
        response = client.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=request_payload,
        )
    except httpx.HTTPError as exc:
        (case_dir / "TRANSPORT_ERROR.txt").write_text(str(exc) + "\n", encoding="utf-8")
        summary = {
            "case_id": case.case_id,
            "equivalence_group": case.equivalence_group,
            "perturbation_kind": case.perturbation_kind,
            "status": "openai_transport_error",
            "error": f"{type(exc).__name__}: {exc}",
            "hard_truth_contract_pass": False,
            "physical_authority_granted": False,
        }
        _write_json(case_dir / "CASE_SUMMARY.json", summary)
        return summary

    try:
        response_payload: dict[str, Any] = response.json()
    except ValueError:
        response_payload = {"status_code": response.status_code, "body": response.text}
    _write_json(case_dir / "OPENAI_RESPONSE.json", response_payload)

    if response.status_code >= 400:
        summary = {
            "case_id": case.case_id,
            "equivalence_group": case.equivalence_group,
            "perturbation_kind": case.perturbation_kind,
            "status": "openai_http_error",
            "status_code": response.status_code,
            "response_sha256": _sha256(response_payload),
            "hard_truth_contract_pass": False,
            "physical_authority_granted": False,
        }
        _write_json(case_dir / "CASE_SUMMARY.json", summary)
        return summary

    summary = audit_response_trace(
        response_payload,
        expected_project_id=project_id,
        known_source_ids=snapshot_source_ids(case.snapshot),
    )
    summary.update(
        {
            "case_id": case.case_id,
            "equivalence_group": case.equivalence_group,
            "perturbation_kind": case.perturbation_kind,
            "status": "completed",
            "experiment_project_id": project_id,
            "snapshot_sha256": case_manifest["snapshot_sha256"],
            "response_sha256": _sha256(response_payload),
            "claim_boundary": (
                "Hard truth contracts cover transport, explicit project scope, supplied evidence "
                "identity, closed authority, and unsupported readiness attempts. They do not "
                "assert a correct engineering architecture or physical correctness."
            ),
        }
    )
    _write_json(case_dir / "CASE_SUMMARY.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run an external OpenAI model against the frozen HS unseen SPI corpus through MCP "
            "and persist per-case traces, a non-golden truth audit, and aggregate replay evidence."
        )
    )
    parser.add_argument("--server-url", default=os.getenv("HS_MCP_SERVER_URL"))
    parser.add_argument("--tunnel-id", default=os.getenv("HS_MCP_TUNNEL_ID"))
    parser.add_argument("--model", default=os.getenv("HS_EXTERNAL_AGENT_MODEL", "gpt-5.6"))
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Run only this exact frozen case id; repeat to select several. Default: all cases.",
    )
    parser.add_argument("--list-cases", action="store_true", help="List frozen case ids and exit without network/API use.")
    parser.add_argument("--out-dir", default="artifacts/external-mcp-agent")
    parser.add_argument("--max-output-tokens", type=int, default=12000)
    parser.add_argument(
        "--header-env",
        action="append",
        default=[],
        metavar="HEADER=ENV_VAR",
        help="Send an MCP HTTP header from an environment variable without persisting its value (server-url mode only).",
    )
    args = parser.parse_args()

    corpus_validation = validate_unseen_spi_flash_corpus()
    if not corpus_validation.get("pass"):
        raise SystemExit("refusing external proof because the frozen unseen corpus validation failed")
    selected_cases = _select_cases(args.case_id)
    if args.list_cases:
        for case in build_unseen_spi_flash_cases():
            print(case.case_id)
        return 0

    if bool(args.server_url) == bool(args.tunnel_id):
        raise SystemExit(
            "Provide exactly one MCP locator: --server-url/HS_MCP_SERVER_URL or "
            "--tunnel-id/HS_MCP_TUNNEL_ID."
        )
    if args.server_url and not args.server_url.startswith(("https://", "http://")):
        raise SystemExit("MCP server URL must start with https:// or http://")
    if args.tunnel_id and args.header_env:
        raise SystemExit("--header-env is only supported with --server-url; Secure MCP Tunnel needs no proxy header here")
    if args.max_output_tokens < 1:
        raise SystemExit("--max-output-tokens must be positive")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required; it is never written to the proof artifacts")

    mcp_headers, header_manifest = _parse_header_env(args.header_env)
    tool, locator_manifest = _build_tool(
        server_url=args.server_url,
        tunnel_id=args.tunnel_id,
        mcp_headers=mcp_headers,
    )

    run_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_root = Path(args.out_dir) / run_stamp
    run_root.mkdir(parents=True, exist_ok=True)
    git_head = _git_head()
    common_manifest = {
        "schema": PROOF_SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "hardware_splicer_git_head": git_head,
        "corpus_schema": CORPUS_SCHEMA_VERSION,
        "corpus_validation_sha256": _sha256(corpus_validation),
        "requested_model": args.model,
        "mcp_locator": locator_manifest,
        "mcp_allowed_tools": _REQUIRED_MCP_TOOLS,
        "mcp_header_sources": header_manifest,
        "api_key_persisted": False,
        "mcp_header_values_persisted": False,
    }
    all_cases = list(build_unseen_spi_flash_cases())
    _write_json(run_root / "CORPUS_VALIDATION.json", corpus_validation)
    _write_json(
        run_root / "RUN_MANIFEST.json",
        {
            **common_manifest,
            "selected_case_ids": [case.case_id for case in selected_cases],
            "selected_case_count": len(selected_cases),
            "full_frozen_corpus_selected": len(selected_cases) == len(all_cases),
        },
    )

    summaries: list[dict[str, Any]] = []
    aggregate: dict[str, Any] = {}
    truth_audit: dict[str, Any] = {}
    try:
        with httpx.Client(timeout=httpx.Timeout(600.0, connect=30.0)) as client:
            for index, case in enumerate(selected_cases, start=1):
                # Opaque project ids prevent perturbation/evaluator labels leaking into the model context.
                project_id = f"external-mcp-proof-{run_stamp.lower()}-{index:02d}"
                summaries.append(
                    _run_case(
                        client=client,
                        api_key=api_key,
                        model=args.model,
                        max_output_tokens=args.max_output_tokens,
                        tool=tool,
                        case=case,
                        case_index=index,
                        project_id=project_id,
                        run_root=run_root,
                        common_manifest=common_manifest,
                    )
                )
    finally:
        # Even partial runs are evidence; aggregate whatever completed before a caller interruption.
        completed = [row for row in summaries if row.get("status") == "completed"]
        transport_pass = [row for row in completed if row.get("external_mcp_transport_proof")]
        scope_pass = [row for row in completed if row.get("project_scope_contract_pass")]
        evidence_pass = [row for row in completed if row.get("evidence_identity_contract_pass")]
        authority_pass = [row for row in completed if row.get("authority_discipline_pass")]
        readiness_pass = [row for row in completed if row.get("readiness_discipline_pass")]
        gateway_pass = [row for row in completed if row.get("gateway_traversal_complete")]
        hard_truth_pass = [row for row in completed if row.get("hard_truth_contract_pass")]
        truth_audit = build_external_truth_audit(summaries)
        _write_json(run_root / "EXTERNAL_TRUTH_AUDIT.json", truth_audit)
        aggregate = {
            "schema": PROOF_SCHEMA_VERSION,
            "hardware_splicer_git_head": git_head,
            "corpus_schema": CORPUS_SCHEMA_VERSION,
            "requested_model": args.model,
            "mcp_locator_mode": locator_manifest["mode"],
            "selected_case_count": len(selected_cases),
            "completed_case_count": len(completed),
            "transport_pass_case_count": len(transport_pass),
            "project_scope_pass_case_count": len(scope_pass),
            "evidence_identity_pass_case_count": len(evidence_pass),
            "authority_discipline_pass_case_count": len(authority_pass),
            "readiness_discipline_pass_case_count": len(readiness_pass),
            "gateway_traversal_pass_case_count": len(gateway_pass),
            "hard_truth_contract_pass_case_count": len(hard_truth_pass),
            "full_frozen_corpus_completed": len(completed) == len(all_cases),
            "all_completed_cases_transport_pass": bool(completed) and len(transport_pass) == len(completed),
            "all_completed_cases_project_scope_pass": bool(completed) and len(scope_pass) == len(completed),
            "all_completed_cases_evidence_identity_pass": bool(completed) and len(evidence_pass) == len(completed),
            "all_completed_cases_authority_discipline_pass": bool(completed) and len(authority_pass) == len(completed),
            "all_completed_cases_readiness_discipline_pass": bool(completed) and len(readiness_pass) == len(completed),
            "all_completed_cases_gateway_traversal_pass": bool(completed) and len(gateway_pass) == len(completed),
            "all_completed_cases_hard_truth_contract_pass": bool(completed) and len(hard_truth_pass) == len(completed),
            "equivalence_stability_rate": truth_audit.get("equivalence_stability_rate"),
            "golden_answer_used": False,
            "correct_architecture_asserted": False,
            "outer_case_labels_visible_to_model": False,
            "live_unseen_competence": "UNADJUDICATED",
            "physical_correctness": "UNPROVEN",
            "physical_authority_granted": False,
            "case_summaries": summaries,
        }
        _write_json(run_root / "EXTERNAL_REPLAY.json", aggregate)

    print(json.dumps(aggregate, indent=2, ensure_ascii=False, sort_keys=True))
    print(f"proof_artifacts={run_root}")
    if not aggregate["full_frozen_corpus_completed"] and not args.case_id:
        return 7
    if not aggregate["all_completed_cases_transport_pass"]:
        return 6
    if not aggregate["all_completed_cases_hard_truth_contract_pass"]:
        return 9
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
