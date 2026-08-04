#!/usr/bin/env python3
"""Run the reference-rich rover through the complete revisioned JARVIS stack.

This is a deterministic validation harness. Model calls and the compose failure are
injected, no device is touched, and every physical authority remains closed.
"""

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

from hardware_splicer.ai_project_conversation_api import (  # noqa: E402
    create_ai_project_conversation_router,
)
from hardware_splicer.ai_project_orchestrator_api import (  # noqa: E402
    create_ai_project_orchestrator_router,
)
from hardware_splicer.ai_project_repair_api import (  # noqa: E402
    create_ai_project_repair_router,
)
from hardware_splicer.ai_project_tool_executor_api import (  # noqa: E402
    create_ai_project_tool_executor_router,
)
from hardware_splicer.engineering_package_api import (  # noqa: E402
    create_engineering_package_router,
)
from hardware_splicer.engineering_package_download_api import (  # noqa: E402
    create_engineering_package_download_router,
)
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


def _llm_payload(content: Mapping[str, Any], *, model: str) -> dict[str, Any]:
    return {
        "ok": True,
        "provider": "golden-fixture",
        "model": model,
        "content": json.dumps(content),
        "usage": {"input_tokens": 0, "output_tokens": 0},
        "cached": False,
    }


def _proposal_llm(prompt: str, **kwargs: object) -> dict[str, Any]:
    if "PROJECT_CONTEXT=" not in prompt or kwargs.get("json_mode") is not True:
        raise AssertionError("proposal call did not use the bounded JSON contract")
    return _llm_payload(
        {
            "summary": "A source-grounded rover controller candidate is ready for review.",
            "requirements": [
                {
                    "id": "req-corridor-rover",
                    "statement": "The candidate must remain a repairable indoor differential-drive rover.",
                    "source_ids": ["e2e-rover-urdf", "linorobot2-hardware"],
                    "assumptions": [],
                },
                {
                    "id": "req-safe-bringup",
                    "statement": "First motion requires a separate current-limited physical bring-up decision.",
                    "source_ids": ["ardurover-hardware"],
                    "assumptions": [],
                },
            ],
            "open_questions": ["What is the verified motor-driver VIH threshold at 3.3 V logic?"],
            "architecture_candidates": [
                {
                    "id": "candidate-golden-rover-controller",
                    "title": "ESP32-S3 differential-drive controller",
                    "summary": "Use the ESP32-S3 for motor/encoder I/O and the Raspberry Pi for ROS 2 autonomy.",
                    "tradeoffs": ["The motor-driver logic threshold must be proven before hardware bring-up."],
                    "assumptions": ["The selected driver can be made 3.3 V compatible."],
                    "source_ids": ["e2e-rover-urdf", "linorobot2-hardware", "e2e-ros-contract"],
                }
            ],
            "actions": [
                {
                    "action_type": "run_compose",
                    "title": "Compile the rover controller candidate",
                    "rationale": "A deterministic compose preview should expose unresolved electrical assumptions.",
                    "inputs": {
                        "phrase": "Compose a 3.3 V ESP32-S3 differential-drive rover controller with dual encoded motors",
                        "module_ids": ["esp32", "motor_driver"],
                        "constraints": {"logic_voltage_v": 3.3},
                    },
                    "source_ids": ["e2e-rover-urdf", "linorobot2-hardware"],
                }
            ],
        },
        model="golden-proposal-v1",
    )


def _repair_llm(prompt: str, **kwargs: object) -> dict[str, Any]:
    if "logic" not in prompt.lower() or kwargs.get("json_mode") is not True:
        raise AssertionError("repair call did not receive the persisted failure context")
    return _llm_payload(
        {
            "summary": "Replace the unproven direct logic interface with a level-compatible successor.",
            "requirements": [
                {
                    "id": "req-prove-vih",
                    "statement": "The motor interface must prove 3.3 V VIH compatibility or add level translation.",
                    "source_ids": ["linorobot2-hardware"],
                    "assumptions": [],
                }
            ],
            "open_questions": ["Which exact motor-driver part number will be used?"],
            "architecture_candidates": [
                {
                    "id": "candidate-golden-rover-repair",
                    "title": "Verified logic-compatible motor interface",
                    "summary": "Select a documented 3.3 V-compatible driver or add explicit translation.",
                    "tradeoffs": ["A translator may add BOM and routing complexity."],
                    "assumptions": [],
                    "source_ids": ["linorobot2-hardware"],
                }
            ],
            "actions": [
                {
                    "action_type": "revise_candidate",
                    "title": "Revise the motor interface",
                    "rationale": "Resolve the exact persisted compose failure without mutating its evidence.",
                    "inputs": {"target": "motor_driver_logic_interface"},
                    "source_ids": ["linorobot2-hardware"],
                },
                {
                    "action_type": "run_compose",
                    "title": "Preview the repaired controller",
                    "rationale": "Run a new deterministic preview only after a fresh human decision.",
                    "inputs": {
                        "phrase": "Compose a level-compatible ESP32-S3 rover motor interface",
                        "constraints": {"logic_voltage_v": 3.3},
                    },
                    "source_ids": ["linorobot2-hardware"],
                },
            ],
        },
        model="golden-repair-v1",
    )


def _conversation_llm(state: Mapping[str, str]):
    def call(prompt: str, **kwargs: object) -> dict[str, Any]:
        action_id = state.get("parent_action_id", "")
        if not action_id or kwargs.get("json_mode") is not True:
            raise AssertionError("conversation call was missing the parent failure identity")
        if action_id not in prompt:
            raise AssertionError("conversation context omitted the persisted failed action")
        return _llm_payload(
            {
                "answer_kind": "decision_briefing",
                "answer": "The rover is not ready for physical bring-up. Review the repair successor, prove the motor-driver logic threshold, and only then request another software preview.",
                "evidence_refs": [
                    {
                        "kind": "tool_result",
                        "id": action_id,
                        "reason": "The persisted compose preview failed on the unproven logic threshold.",
                    },
                    {
                        "kind": "source",
                        "id": "e2e-rover-urdf",
                        "reason": "The pinned rover model establishes the differential-drive topology under review.",
                    },
                ],
                "blockers": [
                    "The exact motor-driver part number and VIH threshold remain unverified.",
                    "No physical continuity, current-limited power, or motion evidence exists.",
                ],
                "recommended_action": {
                    "action_type": "prepare_verification_plan",
                    "title": "Prepare logic-interface verification",
                    "rationale": "Define the evidence required before another preview or any physical bring-up.",
                    "inputs": {"scope": "motor_driver_logic_interface"},
                    "source_ids": ["e2e-rover-urdf", "linorobot2-hardware"],
                },
                "additional_proposals": [],
            },
            model="golden-jarvis-v1",
        )

    return call


def _failing_compose(**kwargs: object) -> dict[str, Any]:
    if kwargs.get("allow_llm_first") is not False:
        raise AssertionError("golden compose unexpectedly enabled LLM-first execution")
    if kwargs.get("export_gerber") is not False:
        raise AssertionError("golden compose unexpectedly enabled Gerber export")
    raise RuntimeError("golden rover logic threshold unresolved: verify motor-driver VIH")


def _initial_snapshot(case: Mapping[str, Any], sources: list[dict[str, Any]]) -> dict[str, Any]:
    intake = dict(case.get("intake") or {})
    return {
        "projectId": "golden-rover",
        "name": "Golden indoor inspection rover",
        "mission": intake.get("goal"),
        "mode": intake.get("mode", "build"),
        "constraints": dict(intake.get("constraints") or {}),
        "available_parts": list(intake.get("available_parts") or []),
        "parts": list(intake.get("available_parts") or []),
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


def _require_ok(response, label: str) -> dict[str, Any]:
    if response.status_code != 200:
        raise RuntimeError(f"{label} failed: {response.status_code} {response.text}")
    payload = response.json()
    if not payload.get("ok", True):
        raise RuntimeError(f"{label} returned a non-ok response: {payload}")
    return payload


def _check(name: str, passed: bool, observed: Any, expected: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "observed": observed, "expected": expected}


def _read_package_json(archive: zipfile.ZipFile, name: str) -> Any:
    return json.loads(archive.read(name).decode("utf-8"))


def run_golden_rover(catalog: Mapping[str, Any], case: Mapping[str, Any], out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    workspace = out_dir / "workspace"
    shutil.rmtree(workspace, ignore_errors=True)

    planner_report = run_robot_reference_e2e(catalog, case)
    sources = selected_engineering_sources(catalog, case)
    source_ids = {str(row.get("source_id") or "") for row in sources}
    required_source_ids = {"e2e-rover-urdf", "linorobot2-hardware", "ardurover-hardware"}
    if not required_source_ids.issubset(source_ids):
        raise RuntimeError(f"golden rover sources are missing: {sorted(required_source_ids - source_ids)}")

    store = ProjectStore(workspace / "projects")
    initial = store.save("golden-rover", _initial_snapshot(case, sources))
    state: dict[str, str] = {}

    app = FastAPI()
    app.include_router(create_ai_project_orchestrator_router(store, llm_callable=_proposal_llm))
    app.include_router(
        create_ai_project_tool_executor_router(store, compose_callable=_failing_compose)
    )
    app.include_router(create_ai_project_repair_router(store, llm_callable=_repair_llm))
    app.include_router(
        create_ai_project_conversation_router(store, llm_callable=_conversation_llm(state))
    )
    app.include_router(create_engineering_package_router(store))
    app.include_router(create_engineering_package_download_router(store))
    client = TestClient(app)

    proposed = _require_ok(
        client.post(
            "/v1/projects/golden-rover/ai-sessions",
            json={
                "mission": str(case.get("intake", {}).get("goal") or "Design the golden rover"),
                "expected_revision": 1,
                "constraints": dict(case.get("intake", {}).get("constraints") or {}),
                "model_profile": "deep_synthesis",
                "max_actions": 4,
            },
        ),
        "proposal creation",
    )
    session = dict(proposed["session"])
    session_id = str(session["session_id"])
    parent_action = dict(session["actions"][0])
    parent_action_id = str(parent_action["action_id"])
    state["parent_action_id"] = parent_action_id

    decided = _require_ok(
        client.post(
            f"/v1/projects/golden-rover/ai-sessions/{session_id}/actions/{parent_action_id}/decision",
            json={
                "expected_revision": 2,
                "decision": "accepted",
                "reviewer": "golden-human-reviewer",
                "note": "Accept as a software proposal only; do not authorize physical action.",
            },
        ),
        "human decision",
    )

    previewed = _require_ok(
        client.post(
            f"/v1/projects/golden-rover/ai-sessions/{session_id}/actions/{parent_action_id}/execute-preview",
            json={"expected_revision": 3},
        ),
        "deterministic preview",
    )

    repaired = _require_ok(
        client.post(
            f"/v1/projects/golden-rover/ai-sessions/{session_id}/actions/{parent_action_id}/repair",
            json={"expected_revision": 4, "max_actions": 4},
        ),
        "bounded repair",
    )
    repair_session = dict(repaired["repair_session"])
    repair_session_id = str(repair_session["session_id"])

    briefed = _require_ok(
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

    packaged = _require_ok(
        client.post(
            "/v1/projects/golden-rover/engineering-packages",
            json={"expected_revision": 6},
        ),
        "Engineering Package export",
    )
    package = dict(packaged["package"])

    replayed = _require_ok(
        client.post(
            "/v1/projects/golden-rover/engineering-packages",
            json={"expected_revision": 6},
        ),
        "Engineering Package replay",
    )

    downloaded = client.get(
        f"/v1/projects/golden-rover/engineering-packages/{package['package_id']}/download"
    )
    if downloaded.status_code != 200:
        raise RuntimeError(
            f"verified package download failed: {downloaded.status_code} {downloaded.text}"
        )
    package_bytes = downloaded.content
    package_copy = out_dir / "GOLDEN_ROVER_ENGINEERING_PACKAGE.zip"
    package_copy.write_bytes(package_bytes)

    with zipfile.ZipFile(BytesIO(package_bytes)) as archive:
        names = set(archive.namelist())
        action_trace = _read_package_json(archive, "ACTION_TRACE.json")
        tool_results = _read_package_json(archive, "TOOL_RESULTS.json")
        repair_lineage = _read_package_json(archive, "REPAIR_LINEAGE.json")
        conversation = _read_package_json(archive, "CONVERSATION_BRIEFINGS.json")
        blockers = _read_package_json(archive, "BLOCKERS.json")
        authority = _read_package_json(archive, "AUTHORITY_STATE.json")
        manifest = _read_package_json(archive, "MANIFEST.json")

    latest = store.load("golden-rover")
    sessions = list(latest["snapshot"].get("engineeringAiSessions") or [])
    saved_parent = next(row for row in sessions if row.get("session_id") == session_id)
    saved_action = next(
        row for row in saved_parent.get("actions") or [] if row.get("action_id") == parent_action_id
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
            "release_authorized",
        )
    }
    raw_marker = str(
        next(
            row.get("content")
            for row in case.get("inline_engineering_sources") or []
            if row.get("source_id") == "e2e-rover-urdf"
        )
    ).encode("utf-8")

    checks = [
        _check("base-reference-planner", planner_report.get("passed") is True, planner_report.get("passed"), True),
        _check("initial-project-revision", initial.get("revision") == 1, initial.get("revision"), 1),
        _check("proposal-revision", proposed.get("revision") == 2, proposed.get("revision"), 2),
        _check("decision-revision", decided.get("revision") == 3, decided.get("revision"), 3),
        _check("preview-failure-revision", previewed.get("revision") == 4, previewed.get("revision"), 4),
        _check("repair-revision", repaired.get("revision") == 5, repaired.get("revision"), 5),
        _check("conversation-revision", briefed.get("revision") == 6, briefed.get("revision"), 6),
        _check("package-record-revision", packaged.get("revision") == 7, packaged.get("revision"), 7),
        _check(
            "persisted-preview-failure",
            saved_action.get("status") == "failed"
            and dict(saved_action.get("tool_result") or {}).get("status") == "failed",
            {"action": saved_action.get("status"), "tool": dict(saved_action.get("tool_result") or {}).get("status")},
            {"action": "failed", "tool": "failed"},
        ),
        _check(
            "repair-lineage-preserved",
            dict(saved_repair.get("repair_of") or {}).get("parent_action_id") == parent_action_id
            and all(row.get("status") == "proposed" for row in saved_repair.get("actions") or []),
            {
                "parent_action_id": dict(saved_repair.get("repair_of") or {}).get("parent_action_id"),
                "statuses": [row.get("status") for row in saved_repair.get("actions") or []],
            },
            {"parent_action_id": parent_action_id, "statuses": ["proposed", "proposed"]},
        ),
        _check(
            "jarvis-grounded-briefing",
            turn.get("answer_kind") == "decision_briefing"
            and any(row.get("kind") == "tool_result" and row.get("id") == parent_action_id for row in turn.get("evidence_refs") or [])
            and bool(turn.get("recommended_action_id")),
            {
                "answer_kind": turn.get("answer_kind"),
                "evidence_refs": turn.get("evidence_refs"),
                "recommended_action_id": turn.get("recommended_action_id"),
            },
            "decision briefing grounded in the failed tool result with one proposed next action",
        ),
        _check(
            "package-replay-idempotent",
            replayed.get("idempotent") is True
            and dict(replayed.get("package") or {}).get("package_id") == package.get("package_id")
            and replayed.get("revision") == 7,
            {
                "idempotent": replayed.get("idempotent"),
                "package_id": dict(replayed.get("package") or {}).get("package_id"),
                "revision": replayed.get("revision"),
            },
            {"idempotent": True, "package_id": package.get("package_id"), "revision": 7},
        ),
        _check("package-required-files", REQUIRED_PACKAGE_FILES.issubset(names), sorted(names), sorted(REQUIRED_PACKAGE_FILES)),
        _check(
            "package-zip-hash",
            hashlib.sha256(package_bytes).hexdigest() == package.get("zip_sha256")
            and len(package_bytes) == package.get("zip_size_bytes"),
            {"sha256": hashlib.sha256(package_bytes).hexdigest(), "size": len(package_bytes)},
            {"sha256": package.get("zip_sha256"), "size": package.get("zip_size_bytes")},
        ),
        _check("raw-rover-source-omitted", raw_marker not in package_bytes, raw_marker[:80].decode("utf-8"), "absent"),
        _check(
            "package-action-trace",
            any(row.get("action_id") == parent_action_id and row.get("status") == "failed" for row in action_trace),
            action_trace,
            "failed parent action present",
        ),
        _check(
            "package-tool-result",
            any(row.get("action_id") == parent_action_id and row.get("status") == "failed" for row in tool_results),
            tool_results,
            "failed deterministic tool result present",
        ),
        _check(
            "package-repair-lineage",
            any(row.get("session_id") == repair_session_id and dict(row.get("repair_of") or {}).get("parent_action_id") == parent_action_id for row in repair_lineage),
            repair_lineage,
            "repair child references failed parent",
        ),
        _check(
            "package-conversation",
            any(row.get("turn_id") == turn.get("turn_id") and row.get("recommended_action_id") == turn.get("recommended_action_id") for row in conversation),
            conversation,
            "persisted JARVIS turn and proposed next action present",
        ),
        _check("package-blockers", len(blockers) >= 3, blockers, ">=3 explicit blockers/questions/failures"),
        _check(
            "manifest-file-count",
            len(manifest.get("files") or []) == package.get("file_count") - 1,
            len(manifest.get("files") or []),
            package.get("file_count") - 1,
        ),
        _check(
            "physical-authority-fail-closed",
            not any(value is True for value in physical.values())
            and authority.get("package_authorizes_physical_action") is False,
            {"project": physical, "package": authority},
            "all project gates false and package grants no physical authority",
        ),
    ]
    passed = all(row["passed"] for row in checks)

    return {
        "schema_version": REPORT_SCHEMA,
        "scenario_id": case.get("scenario_id"),
        "passed": passed,
        "revision_chain": {
            "initial": 1,
            "proposal": proposed.get("revision"),
            "decision": decided.get("revision"),
            "preview_failure": previewed.get("revision"),
            "repair": repaired.get("revision"),
            "conversation": briefed.get("revision"),
            "package_record": packaged.get("revision"),
        },
        "identities": {
            "parent_session_id": session_id,
            "parent_action_id": parent_action_id,
            "repair_session_id": repair_session_id,
            "conversation_turn_id": turn.get("turn_id"),
            "recommended_action_id": turn.get("recommended_action_id"),
            "package_id": package.get("package_id"),
        },
        "package": {
            "path": package_copy.name,
            "source_revision": package.get("source_revision"),
            "snapshot_sha256": package.get("snapshot_sha256"),
            "manifest_sha256": package.get("manifest_sha256"),
            "zip_sha256": package.get("zip_sha256"),
            "zip_size_bytes": package.get("zip_size_bytes"),
            "file_count": package.get("file_count"),
        },
        "base_planner": {
            "passed": planner_report.get("passed"),
            "plan_summary": planner_report.get("plan_summary"),
            "physical_authority": planner_report.get("physical_authority"),
        },
        "physical_authority": physical,
        "checks": checks,
        "limitations": [
            "The proposal, repair, and JARVIS responses are deterministic injected fixtures.",
            "The compose failure is deliberate and validates failure persistence plus repair lineage.",
            "Public and inline references remain declared evidence rather than physical verification.",
            "No fabrication, flashing, energization, motion, operation, or release action is performed.",
            "This harness proves the revisioned software workflow, not real rover hardware readiness.",
        ],
    }


def _markdown(report: Mapping[str, Any]) -> str:
    identities = dict(report.get("identities") or {})
    package = dict(report.get("package") or {})
    revisions = dict(report.get("revision_chain") or {})
    lines = [
        "# Golden Rover JARVIS End-to-End Report",
        "",
        f"**Scenario:** `{report.get('scenario_id')}`",
        f"**Result:** `{'PASS' if report.get('passed') else 'FAIL'}`",
        "",
        "This validates the complete revisioned software workflow. It is not a physical readiness or release certificate.",
        "",
        "## Revision chain",
        "",
    ]
    lines.extend(f"- {key.replace('_', ' ').title()}: `{value}`" for key, value in revisions.items())
    lines.extend(
        [
            "",
            "## Trace identities",
            "",
            f"- Parent session: `{identities.get('parent_session_id')}`",
            f"- Failed action: `{identities.get('parent_action_id')}`",
            f"- Repair session: `{identities.get('repair_session_id')}`",
            f"- JARVIS turn: `{identities.get('conversation_turn_id')}`",
            f"- Recommended action: `{identities.get('recommended_action_id')}`",
            f"- Engineering Package: `{identities.get('package_id')}`",
            "",
            "## Package",
            "",
            f"- Source revision: `{package.get('source_revision')}`",
            f"- Files: `{package.get('file_count')}`",
            f"- ZIP bytes: `{package.get('zip_size_bytes')}`",
            f"- Snapshot SHA-256: `{package.get('snapshot_sha256')}`",
            f"- Manifest SHA-256: `{package.get('manifest_sha256')}`",
            f"- ZIP SHA-256: `{package.get('zip_sha256')}`",
            "",
            "## Acceptance checks",
            "",
            "| Check | Result |",
            "|---|---|",
        ]
    )
    for row in report.get("checks") or []:
        lines.append(f"| {row.get('name')} | {'PASS' if row.get('passed') else 'FAIL'} |")
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

    report = run_golden_rover(load_json(args.catalog), load_json(args.case), args.out)
    json_path = args.out / "GOLDEN_ROVER_JARVIS_E2E.json"
    md_path = args.out / "GOLDEN_ROVER_JARVIS_E2E.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "scenario_id": report.get("scenario_id"),
                "passed": report.get("passed"),
                "revision_chain": report.get("revision_chain"),
                "identities": report.get("identities"),
                "package": report.get("package"),
                "physical_authority": report.get("physical_authority"),
            },
            indent=2,
        )
    )
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    if args.strict and not report.get("passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
