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
                            "powered_off_high_impedance_required": True
                        }
                    },
                    "source_ids": ["dut-datasheet-r1", "fixture-controller-manual-r1", "test-limits-r1"]
                }
            ]
        },
        "golden-semiconductor-repair-v1",
    )


def conversation_llm(state: Mapping[str, str]):
    def _llm(prompt: str, **kwargs: object) -> dict[str, Any]:
        assert kwargs.get("json_mode") is True
        assert "CONVERSATION_CONTEXT=" in prompt
        body = {
            "summary": "The fixture candidate is blocked until the translated DUT interface is re-previewed and passes deterministic checks.",
            "key_points": [
                "The failed direct 3.3 V controller path remains immutable evidence.",
                "The repair candidate proposes a default-off 1.8 V translation boundary.",
            ],
            "open_questions": [
                "Which translator part meets the powered-off high-impedance requirement?"
            ],
            "recommended_next_action_ids": [state["repair_preview_action_id"]],
        }
        return llm_payload(body, "golden-semiconductor-conversation-v1")

    return _llm


class GoldenFixtureComposeAdapter:
    """Deterministic proposal adapter used by the fixture E2E.

    The first preview fails on the intentional 3.3 V -> 1.8 V DUT interface gap.
    The repair preview emits a bounded protected candidate with closed software checks.
    """

    def preview(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        phrase = str(payload.get("phrase") or "").lower()
        protected = "default-off 1.8 v translated" in phrase
        if protected:
            return {
                "ok": True,
                "mode": "fixture_adapter_candidate",
                "schema_version": "hardware_splicer.fixture_adapter_candidate.v1",
                "project_name": "golden_fixture_adapter",
                "candidate_id": "protected-dut-adapter",
                "source_ids": [
                    "dut-datasheet-r1",
                    "dut-pin-map-r1",
                    "socket-drawing-r1",
                    "fixture-controller-manual-r1",
                    "test-limits-r1",
                    "lab-supply-procedure-r1",
                ],
                "interfaces": {
                    "dut_domain_v": 1.8,
                    "controller_domain_v": 3.3,
                    "translator": {
                        "required": True,
                        "powered_off_high_impedance_required": True,
                    },
                },
                "checks": {
                    "dut_overvoltage_path": "closed_by_translator_candidate",
                    "reserved_pins_no_connect": True,
                    "socket_orientation_review": "open_physical_gate",
                    "bench_current_limit_review": "open_physical_gate",
                },
                "warnings": [
                    "Software preview only; translator part number and bench limits still require evidence closure."
                ],
                "authority_effect": "none",
            }
        return {
            "ok": False,
            "mode": "fixture_adapter_candidate",
            "schema_version": "hardware_splicer.fixture_adapter_candidate.v1",
            "project_name": "golden_fixture_adapter",
            "candidate_id": "direct-controller-dut-adapter",
            "source_ids": ["dut-datasheet-r1", "fixture-controller-manual-r1"],
            "error": {
                "code": "fixture_interface_voltage_domain_unclosed",
                "message": "1.8 V DUT interface is not protected from 3.3 V controller outputs and pull-ups.",
            },
            "checks": {
                "dut_overvoltage_path": "blocked",
                "reserved_pins_no_connect": "not_evaluated_after_blocker",
            },
            "authority_effect": "none",
        }


def fixture_app(case: Mapping[str, Any], store: ProjectStore) -> FastAPI:
    app = FastAPI()
    app.include_router(
        create_ai_project_orchestrator_router(
            store=store,
            llm_callable=proposal_llm,
            include_in_schema=False,
        )
    )
    app.include_router(
        create_ai_project_tool_executor_router(
            store=store,
            compose_adapter=GoldenFixtureComposeAdapter(),
            include_in_schema=False,
        )
    )
    app.include_router(
        create_ai_project_repair_router(
            store=store,
            llm_callable=repair_llm,
            include_in_schema=False,
        )
    )
    app.include_router(
        create_ai_project_conversation_router(
            store=store,
            llm_callable=conversation_llm(case["state"]),
            include_in_schema=False,
        )
    )
    app.include_router(create_engineering_package_router(store=store, include_in_schema=False))
    app.include_router(create_engineering_package_download_router(store=store, include_in_schema=False))
    return app


def post_json(client: TestClient, path: str, body: Mapping[str, Any]) -> dict[str, Any]:
    response = client.post(path, json=dict(body))
    if response.status_code != 200:
        raise RuntimeError(f"POST {path} failed: {response.status_code} {response.text}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"POST {path} did not return an object")
    return payload


def require_ok(response, *, label: str) -> dict[str, Any]:
    if response.status_code != 200:
        raise RuntimeError(f"{label} failed: {response.status_code} {response.text}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} did not return an object")
    return payload


def run(case: Mapping[str, Any], out_dir: Path) -> dict[str, Any]:
    out_dir = Path(out_dir).resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    store = ProjectStore(root=out_dir / "store")
    project = store.create_project(
        project_id=str(case["project"]["project_id"]),
        name=str(case["project"]["name"]),
        mode=str(case["project"]["mode"]),
        initial_state=dict(case["project"]["initial_state"]),
    )
    current = store.get_project(project["project_id"])
    case_with_state = dict(case)
    case_with_state["state"] = {}
    app = fixture_app(case_with_state, store)
    client = TestClient(app)

    proposal = require_ok(
        client.post(
            f"/v1/projects/{project['project_id']}/ai/sessions",
            json={
                "project_revision": current["revision"],
                "mission": str(case["mission"]),
                "constraints": dict(case.get("constraints") or {}),
            },
        ),
        label="fixture proposal",
    )
    proposal_session = proposal["session"]
    preview_action = next(
        action
        for action in proposal_session["actions"]
        if action["action_type"] == "run_compose"
    )
    failed_preview = require_ok(
        client.post(
            f"/v1/projects/{project['project_id']}/ai/sessions/{proposal_session['session_id']}/actions/{preview_action['action_id']}/execute",
            json={"project_revision": proposal_session["project_revision"]},
        ),
        label="fixture failed preview",
    )
    failed_action = failed_preview["action"]
    if failed_action["status"] != "failed":
        raise RuntimeError("fixture failed preview unexpectedly passed")

    repaired = require_ok(
        client.post(
            f"/v1/projects/{project['project_id']}/ai/sessions/{proposal_session['session_id']}/actions/{preview_action['action_id']}/repair",
            json={
                "project_revision": proposal_session["project_revision"],
                "repair_iteration": 1,
            },
        ),
        label="fixture repair",
    )
    repair_session = repaired["repair_session"]
    repair_preview_action = next(
        action
        for action in repair_session["actions"]
        if action["action_type"] == "run_compose"
    )
    case_with_state["state"]["repair_preview_action_id"] = repair_preview_action["action_id"]
    repaired_preview = require_ok(
        client.post(
            f"/v1/projects/{project['project_id']}/ai/sessions/{repair_session['session_id']}/actions/{repair_preview_action['action_id']}/execute",
            json={"project_revision": repair_session["project_revision"]},
        ),
        label="fixture repair preview",
    )
    repaired_action = repaired_preview["action"]
    if repaired_action["status"] != "succeeded":
        raise RuntimeError("fixture repair preview did not succeed")

    briefing = require_ok(
        client.post(
            f"/v1/projects/{project['project_id']}/ai/conversations",
            json={
                "project_revision": repaired_action["project_revision"],
                "message": "Summarize what changed, what still blocks fabrication, and the next review action.",
            },
        ),
        label="fixture conversation",
    )

    package = require_ok(
        client.post(
            f"/v1/projects/{project['project_id']}/engineering-package",
            json={
                "project_revision": repaired_action["project_revision"],
                "selected_candidate_id": "candidate-protected-dut-adapter",
                "selected_action_ids": [repair_preview_action["action_id"]],
            },
        ),
        label="fixture package",
    )
    package_id = package["package"]["package_id"]
    download = client.get(
        f"/v1/projects/{project['project_id']}/engineering-package/{package_id}/download"
    )
    if download.status_code != 200:
        raise RuntimeError(
            f"fixture package download failed: {download.status_code} {download.text}"
        )
    zip_bytes = download.content
    zip_path = out_dir / "GOLDEN_SEMICONDUCTOR_FIXTURE_PACKAGE.zip"
    zip_path.write_bytes(zip_bytes)
    with zipfile.ZipFile(BytesIO(zip_bytes), "r") as archive:
        names = set(archive.namelist())
        missing = sorted(PACKAGE_PREFIX + name for name in REQUIRED_PACKAGE_FILES if PACKAGE_PREFIX + name not in names)
        if missing:
            raise RuntimeError(f"fixture package missing required files: {missing}")
        manifest = json.loads(archive.read(PACKAGE_PREFIX + "MANIFEST.json"))
        authority = json.loads(archive.read(PACKAGE_PREFIX + "AUTHORITY_STATE.json"))
        blockers = json.loads(archive.read(PACKAGE_PREFIX + "BLOCKERS.json"))
        repair_lineage = json.loads(archive.read(PACKAGE_PREFIX + "REPAIR_LINEAGE.json"))
        tool_results = json.loads(archive.read(PACKAGE_PREFIX + "TOOL_RESULTS.json"))
        project_brief = json.loads(archive.read(PACKAGE_PREFIX + "PROJECT_BRIEF.json"))
        source_manifest = json.loads(archive.read(PACKAGE_PREFIX + "SOURCE_MANIFEST.json"))
        source_conflicts = json.loads(archive.read(PACKAGE_PREFIX + "SOURCE_CONFLICTS.json"))
        requirements = json.loads(archive.read(PACKAGE_PREFIX + "REQUIREMENTS.json"))
        decisions = json.loads(archive.read(PACKAGE_PREFIX + "DECISIONS.json"))
        action_trace = json.loads(archive.read(PACKAGE_PREFIX + "ACTION_TRACE.json"))
        conversation_briefings = json.loads(archive.read(PACKAGE_PREFIX + "CONVERSATION_BRIEFINGS.json"))
        artifact_references = json.loads(archive.read(PACKAGE_PREFIX + "ARTIFACT_REFERENCES.json"))

    checks = {
        "proposal_revision_pinned": proposal_session["project_revision"] == current["revision"],
        "initial_candidate_visible": any(
            row["id"] == "candidate-direct-controller-adapter"
            for row in proposal_session["architecture_candidates"]
        ),
        "failed_preview_persisted": failed_action["status"] == "failed",
        "failure_code_visible": (
            (((failed_action.get("tool_result") or {}).get("error") or {}).get("code"))
            == "fixture_interface_voltage_domain_unclosed"
        ),
        "repair_lineage_points_to_failure": (
            repair_session["repair_of"]["parent_session_id"] == proposal_session["session_id"]
            and repair_session["repair_of"]["parent_action_id"] == preview_action["action_id"]
            and repair_session["repair_of"]["failure_sha256"]
            == repair_session["architecture_candidates"][0]["lineage"]["failure_sha256"]
        ),
        "repair_successor_visible": repair_session["architecture_candidates"][0]["id"]
        == "candidate-protected-dut-adapter",
        "repair_preview_succeeded": repaired_action["status"] == "succeeded",
        "conversation_grounded_in_repair": (
            briefing["conversation"]["session_id"] == repair_session["session_id"]
            and briefing["conversation"]["recommended_next_action_ids"]
            == [repair_preview_action["action_id"]]
        ),
        "package_manifest_complete": not missing,
        "package_manifest_matches_zip": sorted(manifest["files"]) == sorted(name.removeprefix(PACKAGE_PREFIX) for name in names if name.startswith(PACKAGE_PREFIX) and not name.endswith("/") and name != PACKAGE_PREFIX + "MANIFEST.json"),
        "package_preserves_project_identity": project_brief["project_id"] == project["project_id"],
        "package_preserves_sources": {row["source_id"] for row in source_manifest["sources"]} >= {
            "dut-datasheet-r1",
            "dut-pin-map-r1",
            "socket-drawing-r1",
            "fixture-controller-manual-r1",
            "test-limits-r1",
            "lab-supply-procedure-r1",
        },
        "package_preserves_source_conflicts": source_conflicts["source_conflicts"] == case["project"]["initial_state"]["engineeringSourceConflicts"],
        "package_preserves_requirements": any(
            row["id"] == "req-default-off-translation" for row in requirements["requirements"]
        ),
        "package_preserves_decision": decisions["selected_candidate_id"] == "candidate-protected-dut-adapter",
        "package_preserves_action_trace": any(
            row["action_id"] == repair_preview_action["action_id"] for row in action_trace["actions"]
        ),
        "package_preserves_tool_results": any(
            row.get("status") == "failed"
            and (((row.get("error") or {}).get("code")) == "fixture_interface_voltage_domain_unclosed")
            for row in tool_results["tool_results"]
        )
        and any(row.get("status") == "succeeded" for row in tool_results["tool_results"]),
        "package_preserves_repair_lineage": any(
            row.get("parent_session_id") == proposal_session["session_id"]
            and row.get("parent_action_id") == preview_action["action_id"]
            for row in repair_lineage["repairs"]
        ),
        "package_preserves_conversation": any(
            row.get("session_id") == repair_session["session_id"]
            for row in conversation_briefings["briefings"]
        ),
        "package_preserves_artifact_refs": bool(artifact_references["artifacts"]),
        "fabrication_authority_closed": authority["fabrication_authorized"] is False,
        "flash_authority_closed": authority["firmware_flash_authorized"] is False,
        "power_authority_closed": authority["power_on_authorized"] is False,
        "motion_authority_closed": authority["motion_authorized"] is False,
        "release_authority_closed": authority["release_authorized"] is False,
        "blockers_visible": bool(blockers["blockers"]),
    }

    report = {
        "schema_version": REPORT_SCHEMA,
        "project_id": project["project_id"],
        "project_revision": repaired_action["project_revision"],
        "proposal_session_id": proposal_session["session_id"],
        "repair_session_id": repair_session["session_id"],
        "package_id": package_id,
        "package_zip": str(zip_path),
        "package_sha256": hashlib.sha256(zip_bytes).hexdigest(),
        "checks": checks,
        "pass": all(checks.values()),
    }
    (out_dir / "GOLDEN_SEMICONDUCTOR_FIXTURE_E2E.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    markdown = [
        "# Golden Semiconductor Fixture E2E",
        "",
        f"- project: `{project['project_id']}`",
        f"- proposal session: `{proposal_session['session_id']}`",
        f"- repair session: `{repair_session['session_id']}`",
        f"- package: `{package_id}`",
        f"- package sha256: `{report['package_sha256']}`",
        f"- overall: `{'PASS' if report['pass'] else 'FAIL'}`",
        "",
        "## Checks",
    ]
    markdown.extend(
        f"- {'PASS' if value else 'FAIL'} `{key}`" for key, value in checks.items()
    )
    (out_dir / "GOLDEN_SEMICONDUCTOR_FIXTURE_E2E.md").write_text(
        "\n".join(markdown) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, default=DEFAULT_CASE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = run(load_case(args.case), args.out)
    print(json.dumps(report, indent=2))
    if args.strict and not report["pass"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
