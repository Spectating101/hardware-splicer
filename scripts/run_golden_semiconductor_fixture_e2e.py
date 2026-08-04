#!/usr/bin/env python3
"""Validate the complete JARVIS stack on a semiconductor DUT fixture case."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any, Mapping

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS_DIR = (ROOT / "scripts").resolve()
sys.path = [str(SRC)] + [p for p in sys.path if Path(p).resolve() != SCRIPTS_DIR]

from hardware_splicer.ai_project_conversation_api import create_ai_project_conversation_router  # noqa: E402
from hardware_splicer.ai_project_orchestrator_api import create_ai_project_orchestrator_router  # noqa: E402
from hardware_splicer.ai_project_repair_api import create_ai_project_repair_router  # noqa: E402
from hardware_splicer.ai_project_tool_executor_api import create_ai_project_tool_executor_router  # noqa: E402
from hardware_splicer.engineering_package_api import create_engineering_package_router  # noqa: E402
from hardware_splicer.engineering_package_download_api import create_engineering_package_download_router  # noqa: E402
from hardware_splicer.project_store import ProjectStore  # noqa: E402

DEFAULT_CASE = ROOT / "examples" / "semiconductor_fixture_e2e" / "low_voltage_dut_validation_adapter.json"
DEFAULT_OUT = ROOT / ".artifacts" / "golden_semiconductor_fixture_e2e"
REPORT_SCHEMA = "hardware_splicer.golden_semiconductor_fixture_e2e_report.v1"
PACKAGE_PREFIX = "ENGINEERING_PACKAGE/"
REQUIRED_PACKAGE_FILES = {
    "PROJECT_BRIEF.json",
    "REQUIREMENTS.json",
    "SOURCE_MANIFEST.json",
    "SOURCE_CONFLICTS.json",
    "ARCHITECTURE_CANDIDATES.json",
    "DECISIONS.json",
    "ACTION_TRACE.json",
    "TOOL_RESULTS.json",
    "REPAIR_LINEAGE.json",
    "CONVERSATION_BRIEFINGS.json",
    "BLOCKERS.json",
    "AUTHORITY_STATE.json",
    "ARTIFACT_REFERENCES.json",
    "MANIFEST.json",
    "README.md",
}


def load_case(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("semiconductor fixture case root must be an object")
    return value


def llm_payload(content: Mapping[str, Any], model: str) -> dict[str, Any]:
    return {
        "ok": True,
        "provider": "golden-fixture",
        "model": model,
        "content": json.dumps(content),
        "usage": {},
        "cached": False,
    }


def proposal_llm(prompt: str, **kwargs: object) -> dict[str, Any]:
    assert "PROJECT_CONTEXT=" in prompt
    assert "dut-datasheet-r1" in prompt
    assert "fixture-controller-manual-r1" in prompt
    assert kwargs.get("json_mode") is True
    return llm_payload(
        {
            "summary": "A pre-fabrication DUT adapter candidate is ready for evidence review.",
            "requirements": [
                {
                    "id": "req-dut-domain",
                    "statement": "Every DUT-facing digital signal must remain in the declared 1.8 V domain.",
                    "source_ids": ["dut-datasheet-r1", "dut-pin-map-r1"],
                    "assumptions": [],
                },
                {
                    "id": "req-current-limited-rail",
                    "statement": "The 1.8 V DUT rail must support measured startup and steady-state current limits.",
                    "source_ids": ["dut-datasheet-r1", "test-limits-r1", "lab-supply-procedure-r1"],
                    "assumptions": [],
                },
                {
                    "id": "req-replaceable-socket",
                    "statement": "The socket orientation, keepout, and replaceability constraints must remain visible in the package.",
                    "source_ids": ["socket-drawing-r1"],
                    "assumptions": [],
                },
            ],
            "open_questions": [
                "Is level translation present on every controller-to-DUT path before controller reset defaults can enable pull-ups?"
            ],
            "architecture_candidates": [
                {
                    "id": "candidate-direct-controller-adapter",
                    "title": "Socketed DUT adapter with controller-managed stimulus",
                    "summary": "Provide socket access, controlled 1.8 V power, current monitoring, analog observation, and controller-driven digital tests.",
                    "tradeoffs": [
                        "The candidate is incomplete until every 3.3 V controller path is proven isolated from the 1.8 V DUT."
                    ],
                    "assumptions": [
                        "The fixture controller can safely manage all digital pins after initialization."
                    ],
                    "source_ids": [
                        "dut-datasheet-r1",
                        "dut-pin-map-r1",
                        "socket-drawing-r1",
                        "fixture-controller-manual-r1"
                    ]
                }
            ],
            "actions": [
                {
                    "action_type": "run_compose",
                    "title": "Compile the DUT validation adapter candidate",
                    "rationale": "A deterministic preview must expose any unclosed voltage-domain or protection assumption before fabrication review.",
                    "inputs": {
                        "phrase": "Compose a socketed 1.8 V DUT validation adapter controlled by a 3.3 V USB fixture controller",
                        "module_ids": ["fixture_mcu", "dut_socket", "current_monitor"],
                        "constraints": {
                            "dut_io_v": 1.8,
                            "controller_io_v": 3.3,
                            "dut_absolute_max_pin_v": 2.0
                        }
                    },
                    "source_ids": [
                        "dut-datasheet-r1",
                        "fixture-controller-manual-r1",
                        "test-limits-r1"
                    ]
                }
            ]
        },
        "golden-semiconductor-proposal-v1",
    )


def repair_llm(prompt: str, **kwargs: object) -> dict[str, Any]:
    assert "1.8 v dut interface is not protected from 3.3 v controller" in prompt.lower()
    assert kwargs.get("json_mode") is True
    return llm_payload(
        {
            "summary": "Insert explicit default-off level translation and series protection on every DUT-facing controller signal.",
            "requirements": [
                {
                    "id": "req-default-off-translation",
                    "statement": "Every 3.3 V controller output and pull-up must be isolated from the DUT until 1.8 V translation is powered and enabled.",
                    "source_ids": ["dut-datasheet-r1", "fixture-controller-manual-r1"],
                    "assumptions": []
                },
                {
                    "id": "req-no-connect-reserved",
                    "statement": "Reserved DUT pins must remain no-connect and visible in deterministic checks.",
                    "source_ids": ["dut-pin-map-r1", "test-limits-r1"],
                    "assumptions": []
                }
            ],
            "open_questions": [
                "Which translator part has a guaranteed powered-off high-impedance state for both voltage domains?"
            ],
            "architecture_candidates": [
                {
                    "id": "candidate-protected-dut-adapter",
                    "title": "Default-off translated DUT validation adapter",
                    "summary": "Add 1.8 V referenced level translation, per-line series protection, rail current monitoring, and explicit enable sequencing.",
                    "tradeoffs": [
                        "Additional protection increases BOM, routing density, and validation work."
                    ],
                    "assumptions": [],
                    "source_ids": [
                        "dut-datasheet-r1",
                        "dut-pin-map-r1",
                        "fixture-controller-manual-r1",
                        "test-limits-r1"
                    ]
                }
            ],
            "actions": [
                {
                    "action_type": "revise_candidate",
                    "title": "Add protected 1.8 V translation",
                    "rationale": "Resolve the persisted voltage-domain failure without rewriting its evidence.",
                    "inputs": {
                        "target": "all_controller_to_dut_digital_paths",
                        "required_default_state": "high_impedance"
                    },
                    "source_ids": ["dut-datasheet-r1", "fixture-controller-manual-r1"]
                },
                {
                    "action_type": "run_compose",
                    "title": "Preview the protected adapter",
                    "rationale": "Run a new software preview only after a fresh human review of the successor.",
                    "inputs": {
                        "phrase": "Compose a default-off 1.8 V translated DUT validation adapter",
                        "constraints": {
                            "dut_io_v": 1.8,
                            "controller_io_v": 3.3,
                            "powered_off_high_impedance_required": true
                        }
                    },
                    "source_ids": ["dut-datasheet-r1", "fixture-controller-manual-r1", "test-limits-r1"]
                }
            ]
        },
        "golden-semiconductor-repair-v1",
    )


def conversation_llm(state: Mapping[str, str]):
    def call(prompt: str, **kwargs: object) -> dict[str, Any]:
        action_id = state.get("failed_action_id", "")
        assert action_id and action_id in prompt
        assert "dut-datasheet-r1" in prompt
        assert kwargs.get("json_mode") is True
        return llm_payload(
            {
                "answer_kind": "decision_briefing",
                "answer": "The fixture is not pre-fabrication ready. The direct 3.3 V controller assumption violates the declared 1.8 V DUT domain, and the successor still needs a verified powered-off translation part and sequencing evidence.",
                "evidence_refs": [
                    {
                        "kind": "tool_result",
                        "id": action_id,
                        "reason": "The persisted deterministic preview failed on the unprotected voltage-domain boundary."
                    },
                    {
                        "kind": "source",
                        "id": "dut-datasheet-r1",
                        "reason": "The declared DUT limits prohibit direct 3.3 V drive and cap digital pins at 2.0 V absolute maximum."
                    },
                    {
                        "kind": "source",
                        "id": "fixture-controller-manual-r1",
                        "reason": "The controller manual declares 3.3 V GPIO and reset-time pull-up risk."
                    }
                ],
                "blockers": [
                    "No exact level-translator part and powered-off behavior are proven.",
                    "No deterministic no-connect check for reserved DUT pins has passed.",
                    "No physical resistance, current-limited power, thermal, or functional DUT evidence exists."
                ],
                "recommended_action": {
                    "action_type": "prepare_verification",
                    "title": "Prepare fixture pre-fabrication verification",
                    "rationale": "Define schematic, netlist, sequencing, no-connect, current-limit, and socket-orientation evidence required before fabrication review.",
                    "inputs": {
                        "scope": "dut_voltage_domains_and_fixture_safety",
                        "required_checks": [
                            "powered_off_translation",
                            "reserved_pin_no_connect",
                            "rail_current_limit",
                            "socket_pin1_orientation"
                        ]
                    },
                    "source_ids": [
                        "dut-datasheet-r1",
                        "dut-pin-map-r1",
                        "socket-drawing-r1",
                        "test-limits-r1",
                        "fixture-controller-manual-r1"
                    ]
                },
                "additional_proposals": []
            },
            "golden-semiconductor-jarvis-v1",
        )

    return call


def failing_compose(**kwargs: object) -> dict[str, Any]:
    assert kwargs.get("allow_llm_first") is False
    assert kwargs.get("export_gerber") is False
    raise RuntimeError(
        "1.8 V DUT interface is not protected from 3.3 V controller; direct drive exceeds declared DUT limits"
    )


def initial_snapshot(case: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "projectId": case["project_id"],
        "name": case["name"],
        "mission": case["mission"],
        "mode": case.get("mode", "build"),
        "constraints": dict(case.get("constraints") or {}),
        "available_parts": list(case.get("available_parts") or []),
        "parts": list(case.get("available_parts") or []),
        "engineeringSources": list(case.get("engineering_sources") or []),
        "engineeringParsedSources": [],
        "engineeringSourceParserRuns": [],
        "engineeringSourceConflicts": [],
        "fabrication_authorized": False,
        "firmware_flash_authorized": False,
        "flash_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
        "operational_authorized": False,
        "release_authorized": False
    }


def require_ok(response, label: str) -> dict[str, Any]:
    if response.status_code != 200:
        raise RuntimeError(f"{label} failed: {response.status_code} {response.text}")
    return response.json()


def package_json(archive: zipfile.ZipFile, name: str) -> Any:
    return json.loads(archive.read(f"{PACKAGE_PREFIX}{name}").decode("utf-8"))


def check(name: str, passed: bool, observed: Any, expected: Any) -> dict[str, Any]:
    return {
        "name": name,
        "passed": bool(passed),
        "observed": observed,
        "expected": expected
    }


def run(case: Mapping[str, Any], out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    workspace = out_dir / "workspace"
    shutil.rmtree(workspace, ignore_errors=True)

    project_id = str(case["project_id"])
    expected = dict(case.get("expected") or {})
    sources = list(case.get("engineering_sources") or [])
    source_ids = {str(row.get("source_id") or "") for row in sources}
    required_sources = {
        "dut-datasheet-r1",
        "dut-pin-map-r1",
        "socket-drawing-r1",
        "test-limits-r1",
        "fixture-controller-manual-r1",
        "lab-supply-procedure-r1"
    }
    if source_ids != required_sources:
        raise RuntimeError(
            f"fixture source identities differ: expected {sorted(required_sources)}, got {sorted(source_ids)}"
        )

    store = ProjectStore(workspace / "projects")
    initial = store.save(project_id, initial_snapshot(case))
    state: dict[str, str] = {}
    app = FastAPI()
    app.include_router(create_ai_project_orchestrator_router(store, llm_callable=proposal_llm))
    app.include_router(create_ai_project_tool_executor_router(store, compose_callable=failing_compose))
    app.include_router(create_ai_project_repair_router(store, llm_callable=repair_llm))
    app.include_router(create_ai_project_conversation_router(store, llm_callable=conversation_llm(state)))
    app.include_router(create_engineering_package_router(store))
    app.include_router(create_engineering_package_download_router(store))
    client = TestClient(app)

    proposed = require_ok(
        client.post(
            f"/v1/projects/{project_id}/ai-sessions",
            json={
                "mission": case["mission"],
                "expected_revision": 1,
                "constraints": dict(case.get("constraints") or {}),
                "model_profile": "deep_synthesis",
                "max_actions": 4
            }
        ),
        "fixture proposal"
    )
    parent_session = dict(proposed["session"])
    parent_session_id = str(parent_session["session_id"])
    failed_action_id = str(parent_session["actions"][0]["action_id"])
    state["failed_action_id"] = failed_action_id

    decided = require_ok(
        client.post(
            f"/v1/projects/{project_id}/ai-sessions/{parent_session_id}/actions/{failed_action_id}/decision",
            json={
                "expected_revision": 2,
                "decision": "accepted",
                "reviewer": "golden-fixture-reviewer",
                "note": "Accepted for a software pre-fabrication preview only."
            }
        ),
        "fixture decision"
    )
    previewed = require_ok(
        client.post(
            f"/v1/projects/{project_id}/ai-sessions/{parent_session_id}/actions/{failed_action_id}/execute-preview",
            json={"expected_revision": 3}
        ),
        "fixture preview"
    )
    repaired = require_ok(
        client.post(
            f"/v1/projects/{project_id}/ai-sessions/{parent_session_id}/actions/{failed_action_id}/repair",
            json={"expected_revision": 4, "max_actions": 4}
        ),
        "fixture repair"
    )
    repair_session = dict(repaired["repair_session"])
    repair_session_id = str(repair_session["session_id"])
    briefed = require_ok(
        client.post(
            f"/v1/projects/{project_id}/ai-sessions/{parent_session_id}/turns",
            json={
                "expected_revision": 5,
                "message": "Is this fixture ready for fabrication, and what evidence is still missing?",
                "client_request_id": "golden-semiconductor-fixture-briefing-v1",
                "max_proposals": 2
            }
        ),
        "fixture JARVIS briefing"
    )
    turn = dict(briefed["turn"])
    packaged = require_ok(
        client.post(
            f"/v1/projects/{project_id}/engineering-packages",
            json={"expected_revision": 6}
        ),
        "fixture package export"
    )
    package = dict(packaged["package"])
    replayed = require_ok(
        client.post(
            f"/v1/projects/{project_id}/engineering-packages",
            json={"expected_revision": 6}
        ),
        "fixture package replay"
    )
    downloaded = client.get(
        f"/v1/projects/{project_id}/engineering-packages/{package['package_id']}/download"
    )
    if downloaded.status_code != 200:
        raise RuntimeError(
            f"fixture package download failed: {downloaded.status_code} {downloaded.text}"
        )
    package_bytes = downloaded.content
    package_path = out_dir / "GOLDEN_SEMICONDUCTOR_FIXTURE_PACKAGE.zip"
    package_path.write_bytes(package_bytes)

    with zipfile.ZipFile(BytesIO(package_bytes)) as archive:
        names = {Path(name).name for name in archive.namelist()}
        source_manifest = package_json(archive, "SOURCE_MANIFEST.json")
        requirements = package_json(archive, "REQUIREMENTS.json")["requirements"]
        candidates = package_json(archive, "ARCHITECTURE_CANDIDATES.json")["candidates"]
        actions = package_json(archive, "ACTION_TRACE.json")["actions"]
        tools = package_json(archive, "TOOL_RESULTS.json")["tool_results"]
        repairs = package_json(archive, "REPAIR_LINEAGE.json")["repairs"]
        turns = package_json(archive, "CONVERSATION_BRIEFINGS.json")["turns"]
        blockers = package_json(archive, "BLOCKERS.json")["blockers"]
        authority = package_json(archive, "AUTHORITY_STATE.json")
        manifest = package_json(archive, "MANIFEST.json")

    latest = store.load(project_id)
    sessions = list(latest["snapshot"].get("engineeringAiSessions") or [])
    saved_parent = next(row for row in sessions if row.get("session_id") == parent_session_id)
    saved_action = next(
        row for row in saved_parent["actions"] if row.get("action_id") == failed_action_id
    )
    saved_repair = next(row for row in sessions if row.get("session_id") == repair_session_id)
    physical = {
        key: latest["snapshot"].get(key)
        for key in (
            "fabrication_authorized",
            "firmware_flash_authorized",
            "power_on_authorized",
            "motion_authorized",
            "operational_authorized",
            "release_authorized"
        )
    }
    raw_markers = [
        str(row.get("content") or "").encode("utf-8")
        for row in sources
        if row.get("content")
    ]
    revision_chain = [
        initial["revision"],
        proposed["revision"],
        decided["revision"],
        previewed["revision"],
        repaired["revision"],
        briefed["revision"],
        packaged["revision"]
    ]
    repair_action_types = [str(row.get("action_type")) for row in saved_repair.get("actions") or []]
    registered_sources = source_manifest.get("registered_sources") or []
    raw_fields_present = any(
        "content" in row or "raw" in row or "bytes" in row
        for row in registered_sources
        if isinstance(row, dict)
    )

    checks = [
        check("fixture-source-count", len(sources) == int(expected["source_count"]), len(sources), expected["source_count"]),
        check("revision-chain", revision_chain == [1, 2, 3, 4, 5, 6, 7], revision_chain, [1, 2, 3, 4, 5, 6, 7]),
        check("proposal-action", parent_session["actions"][0]["action_type"] == expected["proposal_action_type"], parent_session["actions"][0]["action_type"], expected["proposal_action_type"]),
        check("persisted-domain-failure", saved_action.get("status") == "failed" and dict(saved_action.get("tool_result") or {}).get("status") == "failed" and expected["failure_contains"] in str(dict(saved_action.get("tool_result") or {}).get("error", {}).get("message") or ""), saved_action.get("tool_result"), expected["failure_contains"]),
        check("repair-successor", dict(saved_repair.get("repair_of") or {}).get("parent_action_id") == failed_action_id and repair_action_types == expected["repair_action_types"] and all(row.get("status") == "proposed" for row in saved_repair.get("actions") or []), {"repair_of": saved_repair.get("repair_of"), "action_types": repair_action_types}, {"parent_action_id": failed_action_id, "action_types": expected["repair_action_types"]}),
        check("jarvis-pre-fab-block", turn.get("answer_kind") == "decision_briefing" and any(row.get("kind") == "tool_result" and row.get("id") == failed_action_id for row in turn.get("evidence_refs") or []) and any(row.get("kind") == "source" and row.get("id") == "dut-datasheet-r1" for row in turn.get("evidence_refs") or []) and bool(turn.get("recommended_action_id")), turn, "grounded blocked briefing with typed verification proposal"),
        check("jarvis-action-type", any(row.get("origin_turn_id") == turn.get("turn_id") and row.get("action_type") == expected["conversation_action_type"] and row.get("status") == "proposed" for row in saved_parent.get("actions") or []), saved_parent.get("actions"), expected["conversation_action_type"]),
        check("package-replay", replayed.get("idempotent") is True and replayed.get("revision") == 7 and dict(replayed.get("package") or {}).get("package_id") == package.get("package_id"), replayed, "verified replay without revision 8"),
        check("package-files", REQUIRED_PACKAGE_FILES.issubset(names), sorted(names), sorted(REQUIRED_PACKAGE_FILES)),
        check("package-hash", hashlib.sha256(package_bytes).hexdigest() == package.get("zip_sha256") and len(package_bytes) == package.get("zip_size_bytes"), {"sha256": hashlib.sha256(package_bytes).hexdigest(), "bytes": len(package_bytes)}, {"sha256": package.get("zip_sha256"), "bytes": package.get("zip_size_bytes")}),
        check("package-source-revision", package.get("source_revision") == expected["source_revision_for_package"], package.get("source_revision"), expected["source_revision_for_package"]),
        check("raw-source-bytes-omitted", not any(marker and marker in package_bytes for marker in raw_markers) and not raw_fields_present and source_manifest.get("raw_source_bytes_included") is False, {"raw_marker_found": any(marker and marker in package_bytes for marker in raw_markers), "raw_fields_present": raw_fields_present, "manifest_flag": source_manifest.get("raw_source_bytes_included")}, "all false"),
        check("package-domain-requirements", any(row.get("id") == "req-dut-domain" for row in requirements) and any(row.get("id") == "req-default-off-translation" for row in requirements), [row.get("id") for row in requirements], ["req-dut-domain", "req-default-off-translation"]),
        check("package-successor-candidate", any(row.get("id") == "candidate-protected-dut-adapter" for row in candidates), [row.get("id") for row in candidates], "candidate-protected-dut-adapter"),
        check("package-failed-action", any(row.get("action_id") == failed_action_id and row.get("status") == "failed" for row in actions), actions, "failed parent action"),
        check("package-failed-tool", any(row.get("action_id") == failed_action_id and row.get("status") == "failed" for row in tools), tools, "failed deterministic preview"),
        check("package-repair-lineage", any(row.get("session_id") == repair_session_id and dict(row.get("repair_of") or {}).get("parent_action_id") == failed_action_id for row in repairs), repairs, "repair child linked to failure"),
        check("package-conversation", any(row.get("turn_id") == turn.get("turn_id") and row.get("recommended_action_id") == turn.get("recommended_action_id") for row in turns), turns, "JARVIS briefing and recommendation"),
        check("package-blockers", len(blockers) >= 5, blockers, ">=5 open questions, failure, and JARVIS blockers"),
        check("manifest-count", len(manifest.get("files") or []) == package.get("file_count") - 1 and package.get("file_count") == expected["package_file_count"], {"manifest_files": len(manifest.get("files") or []), "package_files": package.get("file_count")}, {"manifest_files": expected["package_file_count"] - 1, "package_files": expected["package_file_count"]}),
        check("authority-fail-closed", not any(value is True for value in physical.values()) and authority.get("package_authorizes_physical_action") is False, {"project": physical, "package": authority}, "fabrication, power, operation, and release remain false")
    ]
    passed = all(row["passed"] for row in checks)
    return {
        "schema_version": REPORT_SCHEMA,
        "scenario_id": case["scenario_id"],
        "passed": passed,
        "revision_chain": {
            "initial": 1,
            "proposal": 2,
            "decision": 3,
            "preview_failure": 4,
            "repair": 5,
            "conversation": 6,
            "package_record": 7
        },
        "identities": {
            "parent_session_id": parent_session_id,
            "failed_action_id": failed_action_id,
            "repair_session_id": repair_session_id,
            "conversation_turn_id": turn.get("turn_id"),
            "recommended_action_id": turn.get("recommended_action_id"),
            "package_id": package.get("package_id")
        },
        "package": {
            "path": package_path.name,
            "source_revision": package.get("source_revision"),
            "snapshot_sha256": package.get("snapshot_sha256"),
            "manifest_sha256": package.get("manifest_sha256"),
            "zip_sha256": package.get("zip_sha256"),
            "zip_size_bytes": package.get("zip_size_bytes"),
            "file_count": package.get("file_count")
        },
        "physical_authority": physical,
        "checks": checks,
        "limitations": [
            "The DUT, documents, and parts are synthetic deterministic fixtures.",
            "AI responses are injected schema-shaped fixtures rather than live-model output.",
            "The compose failure is deliberate and validates domain-conflict persistence.",
            "No schematic, PCB, socket, DUT, instrument, or physical measurement is treated as fabricated evidence.",
            "No fabrication, DUT power, firmware flashing, operation, or release is authorized."
        ]
    }


def markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Golden Semiconductor Fixture JARVIS End-to-End Report",
        "",
        f"**Scenario:** `{report.get('scenario_id')}`",
        f"**Result:** `{'PASS' if report.get('passed') else 'FAIL'}`",
        "",
        "This validates a pre-fabrication software workflow. It is not a fabrication or DUT power certificate.",
        "",
        "## Checks",
        "",
        "| Check | Result |",
        "|---|---|"
    ]
    lines.extend(
        f"| {row.get('name')} | {'PASS' if row.get('passed') else 'FAIL'} |"
        for row in report.get("checks") or []
    )
    lines.extend(["", "## Limits", ""])
    lines.extend(f"- {value}" for value in report.get("limitations") or [])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=Path, default=DEFAULT_CASE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    report = run(load_case(args.case), args.out)
    json_path = args.out / "GOLDEN_SEMICONDUCTOR_FIXTURE_E2E.json"
    md_path = args.out / "GOLDEN_SEMICONDUCTOR_FIXTURE_E2E.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "revision_chain": report["revision_chain"],
                "identities": report["identities"],
                "package": report["package"],
                "physical_authority": report["physical_authority"]
            },
            indent=2
        )
    )
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    if args.strict and not report["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
