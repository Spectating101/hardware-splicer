#!/usr/bin/env python3
"""Run an external OpenAI model against Hardware-Splicer only through remote MCP.

This is an evidence harness, not an evaluator. It freezes the product-visible unseen
SPI mission, sends a general-purpose model only that mission plus the four canonical
HS MCP gateway tools, and persists the exact remote-MCP response trace for later
frozen evaluation. It never treats model prose as physical evidence or authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from hardware_splicer.cleanroom_unseen_spi_flash_experiment import (
    SCHEMA_VERSION,
    spi_flash_adapter_snapshot,
)


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


def _parse_header_env(rows: list[str]) -> tuple[dict[str, str], list[dict[str, str]]]:
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


def _mission(project_id: str) -> tuple[dict[str, Any], str, str]:
    snapshot = spi_flash_adapter_snapshot(name="External MCP unseen SPI proof")
    instructions = """You are the external reasoning engine in a frozen Hardware-Splicer proof run.
You do not have Hardware-Splicer source code and must operate the system only through its MCP tools.

Required operating discipline:
1. Start with hs_backend_status.
2. Discover relevant canonical operations with hs_backend_list_operations.
3. Describe unfamiliar operations before invoking them.
4. Work only on the experiment project_id given in the mission. Never inspect, mutate, or delete unrelated projects.
5. Preserve unresolved component identity, electrical limits, package/pinout, translator mapping, supply implementation, and physical evidence as unresolved unless the available HS evidence actually resolves them.
6. Never invent bench measurements, physical observations, fabrication readiness, power-on readiness, or human authorization.
7. A model/tool conclusion is not physical evidence and grants no physical authority.
8. Use deterministic HS checks and evidence surfaces where relevant. Failures are evidence; do not hide or rewrite them.
9. Produce the strongest defensible pre-fabrication project state and next-action package that the available evidence supports.
10. Before finishing, read back the resulting canonical project state and summarize what remains blocked.

This is an experimental run. Do not optimize the case to an expected answer."""
    input_text = (
        "Execute this frozen Hardware-Splicer mission through MCP.\n\n"
        f"experiment_project_id: {project_id}\n"
        f"corpus_schema: {SCHEMA_VERSION}\n"
        "product_visible_snapshot:\n"
        + json.dumps(snapshot, indent=2, ensure_ascii=False, sort_keys=True)
    )
    return snapshot, instructions, input_text


def _extract_summary(response: dict[str, Any]) -> dict[str, Any]:
    output = list(response.get("output") or [])
    mcp_calls = [row for row in output if isinstance(row, dict) and row.get("type") == "mcp_call"]
    call_names = [str(row.get("name") or "") for row in mcp_calls]
    failed = [
        row
        for row in mcp_calls
        if row.get("status") in {"failed", "incomplete"} or row.get("error")
    ]
    missing_gateway_tools = sorted(set(_REQUIRED_MCP_TOOLS).difference(call_names))
    return {
        "response_id": response.get("id"),
        "response_model": response.get("model"),
        "response_status": response.get("status"),
        "mcp_call_count": len(mcp_calls),
        "mcp_tool_names": call_names,
        "failed_mcp_call_count": len(failed),
        "missing_required_gateway_calls": missing_gateway_tools,
        "external_mcp_transport_proof": bool(mcp_calls) and not failed,
        "gateway_traversal_complete": not missing_gateway_tools and not failed,
        "live_unseen_competence": "UNADJUDICATED",
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "claim_boundary": (
            "This artifact proves only what the persisted response trace contains. "
            "Model output is not bench evidence; competence requires the frozen evaluator, "
            "and physical correctness requires revision-bound real measurements."
        ),
        "usage": response.get("usage"),
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a frozen external OpenAI model against HS through remote MCP and persist the trace."
    )
    parser.add_argument("--server-url", default=os.getenv("HS_MCP_SERVER_URL"))
    parser.add_argument("--model", default=os.getenv("HS_EXTERNAL_AGENT_MODEL", "gpt-5.6"))
    parser.add_argument("--project-id", default=None)
    parser.add_argument("--out-dir", default="artifacts/external-mcp-agent")
    parser.add_argument("--max-output-tokens", type=int, default=12000)
    parser.add_argument(
        "--header-env",
        action="append",
        default=[],
        metavar="HEADER=ENV_VAR",
        help="Send an MCP HTTP header from an environment variable without persisting its value.",
    )
    args = parser.parse_args()

    if not args.server_url:
        raise SystemExit("--server-url or HS_MCP_SERVER_URL is required")
    if not args.server_url.startswith(("https://", "http://")):
        raise SystemExit("MCP server URL must start with https:// or http://")
    if args.max_output_tokens < 1:
        raise SystemExit("--max-output-tokens must be positive")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required; it is never written to the proof artifacts")

    run_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    project_id = args.project_id or f"external-mcp-unseen-spi-{run_stamp.lower()}"
    snapshot, instructions, input_text = _mission(project_id)
    mcp_headers, header_manifest = _parse_header_env(args.header_env)

    tool: dict[str, Any] = {
        "type": "mcp",
        "server_label": "hardware_splicer",
        "server_description": (
            "Canonical Hardware-Splicer backend gateway. It exposes project/evidence/verification "
            "operations while remaining authority-neutral."
        ),
        "server_url": args.server_url,
        "allowed_tools": _REQUIRED_MCP_TOOLS,
        "require_approval": "never",
    }
    if mcp_headers:
        tool["headers"] = mcp_headers

    request_payload: dict[str, Any] = {
        "model": args.model,
        "instructions": instructions,
        "input": input_text,
        "tools": [tool],
        "tool_choice": "required",
        "max_output_tokens": args.max_output_tokens,
        "store": False,
    }

    out_dir = Path(args.out_dir) / run_stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(out_dir / "MISSION.json", snapshot)
    manifest = {
        "schema": "hardware_splicer.external_mcp_agent_proof.v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "hardware_splicer_git_head": _git_head(),
        "corpus_schema": SCHEMA_VERSION,
        "project_id": project_id,
        "requested_model": args.model,
        "server_url": _redacted_url(args.server_url),
        "mcp_allowed_tools": _REQUIRED_MCP_TOOLS,
        "mcp_header_sources": header_manifest,
        "mission_sha256": _sha256(snapshot),
        "instructions_sha256": _sha256(instructions),
        "input_sha256": _sha256(input_text),
        "api_key_persisted": False,
        "mcp_header_values_persisted": False,
        "physical_authority_granted": False,
    }
    _write_json(out_dir / "REQUEST_MANIFEST.json", manifest)

    try:
        with httpx.Client(timeout=httpx.Timeout(600.0, connect=30.0)) as client:
            response = client.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=request_payload,
            )
    except httpx.HTTPError as exc:
        (out_dir / "TRANSPORT_ERROR.txt").write_text(str(exc) + "\n", encoding="utf-8")
        raise SystemExit(f"OpenAI transport failed; evidence written under {out_dir}") from exc

    try:
        response_payload = response.json()
    except ValueError:
        response_payload = {"status_code": response.status_code, "body": response.text}

    _write_json(out_dir / "OPENAI_RESPONSE.json", response_payload)
    if response.status_code >= 400:
        _write_json(
            out_dir / "RUN_SUMMARY.json",
            {
                "status": "openai_http_error",
                "status_code": response.status_code,
                "physical_authority_granted": False,
            },
        )
        raise SystemExit(f"OpenAI returned HTTP {response.status_code}; evidence written under {out_dir}")

    summary = _extract_summary(response_payload)
    summary.update(
        {
            "status": "completed",
            "project_id": project_id,
            "hardware_splicer_git_head": manifest["hardware_splicer_git_head"],
            "mission_sha256": manifest["mission_sha256"],
            "response_sha256": _sha256(response_payload),
        }
    )
    _write_json(out_dir / "RUN_SUMMARY.json", summary)

    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    print(f"proof_artifacts={out_dir}")
    return 0 if summary["external_mcp_transport_proof"] else 6


if __name__ == "__main__":
    raise SystemExit(main())
