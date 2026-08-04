#!/usr/bin/env python3
"""Validate the complete revisioned JARVIS workflow on the golden rover case."""

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
from hardware_splicer.robot_reference_e2e import (  # noqa: E402
    load_json,
    run_robot_reference_e2e,
    selected_engineering_sources,
)

DEFAULT_CATALOG = ROOT / "examples" / "robot_reference_corpus" / "robot_reference_catalog.json"
DEFAULT_CASE = ROOT / "examples" / "robot_reference_e2e" / "reference_rich_indoor_inspection_rover.json"
DEFAULT_OUT = ROOT / ".artifacts" / "golden_rover_jarvis_e2e"
REPORT_SCHEMA = "hardware_splicer.golden_rover_jarvis_e2e_report.v1"
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
    assert kwargs.get("json_mode") is True
    return llm_payload(
        {
            "summary": "A source-grounded rover controller candidate is ready for review.",
            "requirements": [
                {
                    "id": "req-rover-topology",
                    "statement": "Retain the repairable indoor differential-drive rover topology.",
                    "source_ids": ["e2e-rover-urdf", "linorobot2-hardware"],
                    "assumptions": [],
                },
                {
                    "id": "req-safe-bringup",
                    "statement": "First motion remains a separate current-limited physical decision.",
                    "source_ids": ["ardurover-hardware"],
                    "assumptions": [],
                },
            ],
            "open_questions": ["What is the verified motor-driver VIH threshold at 3.3 V?"],
            "architecture_candidates": [
                {
                    "id": "candidate-golden-rover-controller",
                    "title": "ESP32-S3 differential-drive controller",
                    "summary": "Use the ESP32-S3 for motor and encoder I/O and the Raspberry Pi for ROS 2.",
                    "tradeoffs": ["The driver logic threshold must be proven."],
                    "assumptions": ["A 3.3 V-compatible interface can be selected."],
                    "source_ids": ["e2e-rover-urdf", "linorobot2-hardware", "e2e-ros-contract"],
                }
            ],
            "actions": [
                {
                    "action_type": "run_compose",
                    "title": "Compile the rover controller candidate",
                    "rationale": "A deterministic preview should expose unresolved electrical assumptions.",
                    "inputs": {
                        "phrase": "Compose a 3.3 V ESP32-S3 differential-drive rover controller",
                        "module_ids": ["esp32", "motor_driver"],
                        "constraints": {"logic_voltage_v": 3.3},
                    },
                    "source_ids": ["e2e-rover-urdf", "linorobot2-hardware"],
                }
            ],
        },
        "golden-proposal-v1",
    )


def repair_llm(prompt: str, **kwargs: object) -> dict[str, Any]:
    assert "logic" in prompt.lower()
    assert kwargs.get("json_mode") is True
    return llm_payload(
        {
            "summary": "Replace the unproven direct interface with a level-compatible successor.",
            "requirements": [
                {
                    "id": "req-prove-vih",
                    "statement": "Prove 3.3 V VIH compatibility or add level translation.",
                    "source_ids": ["linorobot2-hardware"],
                    "assumptions": [],
                }
            ],
            "open_questions": ["Which exact motor-driver part number will be used?"],
            "architecture_candidates": [
                {
                    "id": "candidate-golden-rover-repair",
                    "title": "Verified logic-compatible motor interface",
                    "summary": "Select a documented compatible driver or add explicit translation.",
                    "tradeoffs": ["Translation may add BOM and routing complexity."],
                    "assumptions": [],
                    "source_ids": ["linorobot2-hardware"],
                }
            ],
            "actions": [
                {
                    "action_type": "revise_candidate",
                    "title": "Revise the motor interface",
                    "rationale": "Resolve the persisted failure without mutating its evidence.",
                    "inputs": {"target": "motor_driver_logic_interface"},
                    "source_ids": ["linorobot2-hardware"],
                },
                {
                    "action_type": "run_compose",
                    "title": "Preview the repaired controller",
                    "rationale": "Run a new preview only after a fresh human decision.",
                    "inputs": {
                        "phrase": "Compose a level-compatible ESP32-S3 rover motor interface",
                        "constraints": {"logic_voltage_v": 3.3},
                    },
                    "source_ids": ["linorobot2-hardware"],
                },
            ],
        },
        "golden-repair-v1",
    )


def conversation_llm(state: Mapping[str, str]):
    def call(prompt: str, **kwargs: object) -> dict[str, Any]:
        action_id = state.get("parent_action_id", "")
        assert action_id and action_id in prompt
        assert kwargs.get("json_mode") is True
        return llm_payload(
            {
                "answer_kind": "decision_briefing",
                "answer": "The rover is not ready for physical bring-up. Review the repair, prove the logic threshold, and then request another software preview.",
                "evidence_refs": [
                    {
                        "kind": "tool_result",
                        "id": action_id,
                        "reason": "The persisted compose preview failed on the unproven threshold.",
                    },
                    {
                        "kind": "source",
                        "id": "e2e-rover-urdf",
                        "reason": "The pinned model establishes the differential-drive topology.",
                    },
                ],
                "blockers": [
                    "The exact driver and VIH threshold remain unverified.",
                    "No continuity, current-limited power, or motion evidence exists.",
                ],
                "recommended_action": {
                    "action_type": "prepare_verification",
                    "title": "Prepare logic-interface verification",
                    "rationale": "Define the evidence required before another preview or bring-up.",
                    "inputs": {"scope": "motor_driver_logic_interface"},
                    "source_ids": ["e2e-rover-urdf", "linorobot2-hardware"],
                },
                "additional_proposals": [],
            },
            "golden-jarvis-v1",
        )

    return call


def failing_compose(**kwargs: object) -> dict[str, Any]:
    assert kwargs.get("allow_llm_first") is False
    assert kwargs.get("export_gerber") is False
    raise RuntimeError("golden rover logic threshold unresolved: verify motor-driver VIH")


def initial_snapshot(case: Mapping[str, Any], sources: list[dict[str, Any]]) -> dict[str, Any]:
    intake = dict(case.get("intake") or {})
    parts = list(intake.get("available_parts") or [])
    return {
        "projectId": "golden-rover",
        "name": "Golden indoor inspection rover",
        "mission": intake.get("goal"),
        "mode": intake.get("mode", "build"),
        "constraints": dict(intake.get("constraints") or {}),
        "available_parts": parts,
        "parts": parts,
        "engineeringSources": sources,
        "engineeringParsedSources": [],
        "engineeringSourceParserRuns": [],
        "engineeringSourceConflicts": [],
        "fabrication_authorized": False,
        "firmware_flash_authorized": False,
        "flash_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
        "operational_authorized": False,
        "release_authorized": False,
    }


def require_ok(response, label: str) -> dict[str, Any]:
    if response.status_code != 200:
        raise RuntimeError(f"{label} failed: {response.status_code} {response.text}")
    return response.json()


def package_json(archive: zipfile.ZipFile, name: str) -> Any:
    return json.loads(archive.read(f"{PACKAGE_PREFIX}{name}").decode("utf-8"))


def check(name: str, passed: bool, observed: Any, expected: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "observed": observed, "expected": expected}


def run(catalog: Mapping[str, Any], case: Mapping[str, Any], out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    workspace = out_dir / "workspace"
    shutil.rmtree(workspace, ignore_errors=True)

    base = run_robot_reference_e2e(catalog, case)
    sources = selected_engineering_sources(catalog, case)
    source_ids = {str(row.get("source_id") or "") for row in sources}
    required_sources = {"e2e-rover-urdf", "linorobot2-hardware", "ardurover-hardware"}
    if not required_sources.issubset(source_ids):
        raise RuntimeError(f"missing golden sources: {sorted(required_sources - source_ids)}")

    store = ProjectStore(workspace / "projects")
    initial = store.save("golden-rover", initial_snapshot(case, sources))
    state: dict[str, str] = {}
    app = FastAPI()
    app.include_router(create_ai_project_orchestrator_router(store, llm_callable=proposal_llm))
    app.include_router(create_ai_project_tool_executor_router(store, compose_callable=failing_compose))
    app.include_router(create_ai_project_repair_router(store, llm_callable=repair_llm))
    app.include_router(create_ai_project_conversation_router(store, llm_callable=conversation_llm(state)))
    app.include_router(create_engineering_package_router(store))
    app.include_router(create_engineering_package_download_router(store))
    client = TestClient(app)

    intake = dict(case.get("intake") or {})
    proposed = require_ok(
        client.post(
            "/v1/projects/golden-rover/ai-sessions",
            json={
                "mission": str(intake.get("goal") or "Design the golden rover"),
                "expected_revision": 1,
                "constraints": dict(intake.get("constraints") or {}),
                "model_profile": "deep_synthesis",
                "max_actions": 4,
            },
        ),
        "proposal",
    )
    parent_session = dict(proposed["session"])
    session_id = str(parent_session["session_id"])
    action_id = str(parent_session["actions"][0]["action_id"])
    state["parent_action_id"] = action_id

    decided = require_ok(
        client.post(
            f"/v1/projects/golden-rover/ai-sessions/{session_id}/actions/{action_id}/decision",
            json={
                "expected_revision": 2,
                "decision": "accepted",
                "reviewer": "golden-human-reviewer",
                "note": "Accepted for software preview only.",
            },
        ),
        "decision",
    )
    previewed = require_ok(
        client.post(
            f"/v1/projects/golden-rover/ai-sessions/{session_id}/actions/{action_id}/execute-preview",
            json={"expected_revision": 3},
        ),
        "preview",
    )
    repaired = require_ok(
        client.post(
            f"/v1/projects/golden-rover/ai-sessions/{session_id}/actions/{action_id}/repair",
            json={"expected_revision": 4, "max_actions": 4},
        ),
        "repair",
    )
    repair_session = dict(repaired["repair_session"])
    repair_session_id = str(repair_session["session_id"])
    briefed = require_ok(
        client.post(
            f"/v1/projects/golden-rover/ai-sessions/{session_id}/turns",
            json={
                "expected_revision": 5,
                "message": "Is the rover ready, and what should we do next?",
                "client_request_id": "golden-rover-briefing-v1",
                "max_proposals": 2,
            },
        ),
        "JARVIS briefing",
    )
    turn = dict(briefed["turn"])
    packaged = require_ok(
        client.post(
            "/v1/projects/golden-rover/engineering-packages",
            json={"expected_revision": 6},
        ),
        "package export",
    )
    package = dict(packaged["package"])
    replayed = require_ok(
        client.post(
            "/v1/projects/golden-rover/engineering-packages",
            json={"expected_revision": 6},
        ),
        "package replay",
    )
    downloaded = client.get(
        f"/v1/projects/golden-rover/engineering-packages/{package['package_id']}/download"
    )
    if downloaded.status_code != 200:
        raise RuntimeError(f"download failed: {downloaded.status_code} {downloaded.text}")
    package_bytes = downloaded.content
    package_path = out_dir / "GOLDEN_ROVER_ENGINEERING_PACKAGE.zip"
    package_path.write_bytes(package_bytes)

    with zipfile.ZipFile(BytesIO(package_bytes)) as archive:
        names = {Path(name).name for name in archive.namelist()}
        actions = package_json(archive, "ACTION_TRACE.json")["actions"]
        tools = package_json(archive, "TOOL_RESULTS.json")["tool_results"]
        repairs = package_json(archive, "REPAIR_LINEAGE.json")["repairs"]
        turns = package_json(archive, "CONVERSATION_BRIEFINGS.json")["turns"]
        blockers = package_json(archive, "BLOCKERS.json")["blockers"]
        authority = package_json(archive, "AUTHORITY_STATE.json")
        manifest = package_json(archive, "MANIFEST.json")

    latest = store.load("golden-rover")
    sessions = list(latest["snapshot"].get("engineeringAiSessions") or [])
    saved_parent = next(row for row in sessions if row.get("session_id") == session_id)
    saved_action = next(row for row in saved_parent["actions"] if row.get("action_id") == action_id)
    saved_repair = next(row for row in sessions if row.get("session_id") == repair_session_id)
    physical = {
        key: latest["snapshot"].get(key)
        for key in (
            "fabrication_authorized",
            "firmware_flash_authorized",
            "power_on_authorized",
            "motion_authorized",
            "operational_authorized",
            "release_authorized",
        )
    }
    raw_urdf = next(
        str(row.get("content") or "")
        for row in case.get("inline_engineering_sources") or []
        if row.get("source_id") == "e2e-rover-urdf"
    ).encode("utf-8")

    revisions = [
        initial["revision"],
        proposed["revision"],
        decided["revision"],
        previewed["revision"],
        repaired["revision"],
        briefed["revision"],
        packaged["revision"],
    ]
    checks = [
        check("base-reference-planner", base.get("passed") is True, base.get("passed"), True),
        check("revision-chain", revisions == [1, 2, 3, 4, 5, 6, 7], revisions, [1, 2, 3, 4, 5, 6, 7]),
        check("persisted-preview-failure", saved_action.get("status") == "failed" and dict(saved_action.get("tool_result") or {}).get("status") == "failed", {"action": saved_action.get("status"), "tool": dict(saved_action.get("tool_result") or {}).get("status")}, {"action": "failed", "tool": "failed"}),
        check("repair-lineage", dict(saved_repair.get("repair_of") or {}).get("parent_action_id") == action_id and all(row.get("status") == "proposed" for row in saved_repair.get("actions") or []), saved_repair.get("repair_of"), action_id),
        check("jarvis-evidence", turn.get("answer_kind") == "decision_briefing" and any(row.get("kind") == "tool_result" and row.get("id") == action_id for row in turn.get("evidence_refs") or []) and bool(turn.get("recommended_action_id")), turn, "grounded decision briefing with typed proposal"),
        check("package-replay", replayed.get("idempotent") is True and replayed.get("revision") == 7 and dict(replayed.get("package") or {}).get("package_id") == package.get("package_id"), replayed, "verified idempotent replay at revision 7"),
        check("package-files", REQUIRED_PACKAGE_FILES.issubset(names), sorted(names), sorted(REQUIRED_PACKAGE_FILES)),
        check("package-hash", hashlib.sha256(package_bytes).hexdigest() == package.get("zip_sha256") and len(package_bytes) == package.get("zip_size_bytes"), {"sha256": hashlib.sha256(package_bytes).hexdigest(), "bytes": len(package_bytes)}, {"sha256": package.get("zip_sha256"), "bytes": package.get("zip_size_bytes")}),
        check("raw-source-omitted", raw_urdf not in package_bytes, "absent" if raw_urdf not in package_bytes else "present", "absent"),
        check("package-action-trace", any(row.get("action_id") == action_id and row.get("status") == "failed" for row in actions), actions, "failed parent action"),
        check("package-tool-result", any(row.get("action_id") == action_id and row.get("status") == "failed" for row in tools), tools, "failed deterministic result"),
        check("package-repair", any(row.get("session_id") == repair_session_id and dict(row.get("repair_of") or {}).get("parent_action_id") == action_id for row in repairs), repairs, "repair child linked to failed parent"),
        check("package-conversation", any(row.get("turn_id") == turn.get("turn_id") and row.get("recommended_action_id") == turn.get("recommended_action_id") for row in turns), turns, "JARVIS turn and recommendation"),
        check("package-blockers", len(blockers) >= 3, blockers, ">=3 blockers/questions/failures"),
        check("manifest-count", len(manifest.get("files") or []) == package.get("file_count") - 1, len(manifest.get("files") or []), package.get("file_count") - 1),
        check("authority-fail-closed", not any(value is True for value in physical.values()) and authority.get("package_authorizes_physical_action") is False, {"project": physical, "package": authority}, "all physical gates false"),
    ]
    passed = all(row["passed"] for row in checks)
    return {
        "schema_version": REPORT_SCHEMA,
        "scenario_id": case.get("scenario_id"),
        "passed": passed,
        "revision_chain": {"initial": 1, "proposal": 2, "decision": 3, "preview_failure": 4, "repair": 5, "conversation": 6, "package_record": 7},
        "identities": {
            "parent_session_id": session_id,
            "parent_action_id": action_id,
            "repair_session_id": repair_session_id,
            "conversation_turn_id": turn.get("turn_id"),
            "recommended_action_id": turn.get("recommended_action_id"),
            "package_id": package.get("package_id"),
        },
        "package": {
            "path": package_path.name,
            "source_revision": package.get("source_revision"),
            "snapshot_sha256": package.get("snapshot_sha256"),
            "manifest_sha256": package.get("manifest_sha256"),
            "zip_sha256": package.get("zip_sha256"),
            "zip_size_bytes": package.get("zip_size_bytes"),
            "file_count": package.get("file_count"),
        },
        "base_planner": {"passed": base.get("passed"), "plan_summary": base.get("plan_summary")},
        "physical_authority": physical,
        "checks": checks,
        "limitations": [
            "AI responses are deterministic injected fixtures.",
            "The compose failure is deliberate and validates repair lineage.",
            "References are declared evidence, not physical verification.",
            "No fabrication, flashing, energization, motion, operation, or release occurs.",
        ],
    }


def markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Golden Rover JARVIS End-to-End Report",
        "",
        f"**Scenario:** `{report.get('scenario_id')}`",
        f"**Result:** `{'PASS' if report.get('passed') else 'FAIL'}`",
        "",
        "This validates the revisioned software workflow, not physical readiness.",
        "",
        "## Checks",
        "",
        "| Check | Result |",
        "|---|---|",
    ]
    lines.extend(f"| {row.get('name')} | {'PASS' if row.get('passed') else 'FAIL'} |" for row in report.get("checks") or [])
    lines.extend(["", "## Limits", ""])
    lines.extend(f"- {value}" for value in report.get("limitations") or [])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--case", type=Path, default=DEFAULT_CASE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = run(load_json(args.catalog), load_json(args.case), args.out)
    json_path = args.out / "GOLDEN_ROVER_JARVIS_E2E.json"
    md_path = args.out / "GOLDEN_ROVER_JARVIS_E2E.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(markdown(report), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "revision_chain": report["revision_chain"], "identities": report["identities"], "package": report["package"], "physical_authority": report["physical_authority"]}, indent=2))
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    if args.strict and not report["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
