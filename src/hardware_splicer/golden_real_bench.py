"""Golden real S3 path — typed donor contract evidence plus physical bench capture."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping

from .bench_capture_bridge import submit_bench_capture, sync_bench_session_template
from .project_intake import splice_and_build_from_intake
from .splice_bench import bench_status, open_bench_session, submit_bench_measurements

SCHEMA = "hardware_splicer.splice_golden_real.v2"
REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = REPO_ROOT / "tests" / "data" / "golden"
DEFAULT_PHOTO = GOLDEN_DIR / "rc_toy_motor_board.jpg"
DEFAULT_CAPTURE = GOLDEN_DIR / "rc_motor_manual_bench_capture.v1.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_golden_bench_capture(path: str | Path | None = None) -> Dict[str, Any]:
    capture_path = Path(path or DEFAULT_CAPTURE).resolve()
    if not capture_path.is_file():
        raise FileNotFoundError(f"golden bench capture not found: {capture_path}")
    data = json.loads(capture_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("golden bench capture must be a JSON object")
    return data


def _template_measurements(template: Mapping[str, Any]) -> List[Dict[str, Any]]:
    return [row for row in (template.get("measurements") or []) if isinstance(row, dict)]


def filter_capture_for_template(capture: Mapping[str, Any], template: Mapping[str, Any]) -> Dict[str, Any]:
    """Bind committed capture rows to the current build's measurable gate IDs.

    Legacy rows may name a stable gate directly. Evidence-recipe rows bind by the
    pair ``interface_id`` + ``measurement_id`` so regenerated gate slugs do not
    invalidate a physical capture packet.
    """
    template_rows = _template_measurements(template)
    allowed = {str(row.get("gate_id") or "") for row in template_rows if row.get("gate_id")}
    by_measurement: Dict[str, List[Dict[str, Any]]] = {}
    for row in template_rows:
        measurement_id = str(row.get("measurement_id") or "").strip()
        if measurement_id:
            by_measurement.setdefault(measurement_id, []).append(row)

    rows: List[Dict[str, Any]] = []
    unmatched: List[Dict[str, Any]] = []
    for raw in capture.get("measurements") or []:
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        gate_id = str(row.get("gate_id") or "").strip()
        if gate_id and gate_id in allowed:
            rows.append(row)
            continue

        measurement_id = str(row.get("measurement_id") or "").strip()
        candidates = list(by_measurement.get(measurement_id) or [])
        interface_id = str(row.get("interface_id") or "").strip()
        if interface_id:
            candidates = [
                candidate
                for candidate in candidates
                if str(candidate.get("interface_id") or "") == interface_id
            ]
        if len(candidates) == 1:
            row["gate_id"] = str(candidates[0].get("gate_id") or "")
            rows.append(row)
        else:
            unmatched.append(row)

    body = dict(capture)
    body["measurements"] = rows
    body["filtered_for_template"] = True
    body["matched_gate_count"] = len(rows)
    body["unmatched_measurements"] = unmatched
    return body


def _interface_packages(build_dir: Path) -> List[Dict[str, Any]]:
    package = _read_json(build_dir / "SPLICE_PLAN.json")
    integrations = package.get("evidence_integrations")
    if not isinstance(integrations, Mapping):
        return []
    return [row for row in (integrations.get("interfaces") or []) if isinstance(row, dict)]


def _resolve_interface_id(build_dir: Path, update: Mapping[str, Any]) -> str:
    packages = _interface_packages(build_dir)
    requested = str(update.get("interface_id") or "").strip()
    if requested and any(
        str((row.get("interface_contract") or {}).get("interface_id") or "") == requested
        for row in packages
    ):
        return requested

    selector = update.get("interface_selector") if isinstance(update.get("interface_selector"), Mapping) else {}
    board_id = str(selector.get("board_id") or "").strip()
    block_id = str(selector.get("block_id") or "").strip()
    role_contains = str(selector.get("functional_role_contains") or "").strip().lower()
    reference_module_id = str(selector.get("reference_module_id") or "").strip()

    matches: List[str] = []
    for row in packages:
        contract = row.get("interface_contract") if isinstance(row.get("interface_contract"), Mapping) else {}
        if board_id and str(contract.get("board_id") or "") != board_id:
            continue
        if block_id and str(contract.get("block_id") or "") != block_id:
            continue
        if role_contains and role_contains not in str(contract.get("functional_role") or "").lower():
            continue
        if reference_module_id:
            references = contract.get("reference_equivalents") or []
            if not any(
                isinstance(ref, Mapping) and str(ref.get("module_id") or "") == reference_module_id
                for ref in references
            ):
                continue
        interface_id = str(contract.get("interface_id") or "").strip()
        if interface_id:
            matches.append(interface_id)

    if len(matches) == 1:
        return matches[0]
    available = [
        str((row.get("interface_contract") or {}).get("interface_id") or "")
        for row in packages
    ]
    raise ValueError(
        f"could not resolve one donor interface for update; requested={requested!r}, "
        f"selector={dict(selector)!r}, matches={matches!r}, available={available!r}"
    )


def _open_contract_gate(session: Mapping[str, Any], interface_id: str) -> Dict[str, Any] | None:
    for gate in session.get("gates") or []:
        if not isinstance(gate, dict):
            continue
        if str(gate.get("status") or "open") == "closed":
            continue
        if not gate.get("requires_contract_edit"):
            continue
        if str(gate.get("interface_id") or "") == interface_id:
            return gate
    return None


def apply_capture_contract_updates(build_dir: str | Path, capture: Mapping[str, Any]) -> Dict[str, Any]:
    """Persist capture-authored interface updates through the real Bench authority path."""
    root = Path(build_dir).resolve()
    updates = [row for row in (capture.get("contract_updates") or []) if isinstance(row, dict)]
    session = bench_status(root)
    contract_actions = [
        gate
        for gate in (session.get("gates") or [])
        if isinstance(gate, dict)
        and gate.get("requires_contract_edit")
        and str(gate.get("status") or "open") != "closed"
    ]
    if contract_actions and not updates:
        return {
            "ok": False,
            "error": "golden_capture_missing_contract_updates",
            "required_contract_action_count": len(contract_actions),
            "applied": [],
            "bench_session": session,
        }

    applied: List[Dict[str, Any]] = []
    for index, raw in enumerate(updates):
        interface_id = _resolve_interface_id(root, raw)
        session = bench_status(root)
        gate = _open_contract_gate(session, interface_id)
        if gate is None:
            applied.append(
                {
                    "index": index,
                    "interface_id": interface_id,
                    "ok": False,
                    "error": "no_open_contract_gate",
                }
            )
            return {"ok": False, "applied": applied, "bench_session": session}

        contract_update = dict(raw)
        contract_update.pop("interface_selector", None)
        contract_update["interface_id"] = interface_id
        updated = submit_bench_measurements(
            root,
            [
                {
                    "gate_id": str(gate.get("gate_id") or ""),
                    "status": "verified",
                    "contract_update": contract_update,
                }
            ],
        )
        submission = list(((updated.get("last_submission") or {}).get("applied") or []))
        result = submission[-1] if submission else {"ok": False, "error": "missing_submission_result"}
        row = {
            "index": index,
            "interface_id": interface_id,
            "gate_id": gate.get("gate_id"),
            **dict(result),
        }
        applied.append(row)
        if not result.get("ok"):
            return {"ok": False, "applied": applied, "bench_session": updated}

    final = bench_status(root)
    return {"ok": True, "applied": applied, "bench_session": final}


def _authority_summary(build_dir: Path) -> Dict[str, Any]:
    package = _read_json(build_dir / "SPLICE_PLAN.json")
    integrations = package.get("evidence_integrations")
    authority = integrations.get("authority") if isinstance(integrations, Mapping) else {}
    return dict(authority) if isinstance(authority, Mapping) else {}


def run_splice_golden_real(
    intake: Mapping[str, Any],
    *,
    out_dir: str | Path,
    capture_path: str | Path | None = None,
    export_gerber: bool = False,
    request_id: str | None = None,
) -> Dict[str, Any]:
    """Build, persist typed donor contracts, then submit physical measurements."""
    out_path = Path(out_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    build = splice_and_build_from_intake(
        intake,
        out_dir=out_path,
        export_gerber=export_gerber,
        request_id=request_id,
    )
    before = open_bench_session(out_path, force=True)
    golden = load_golden_bench_capture(capture_path)

    contract_result = apply_capture_contract_updates(out_path, golden)
    after_contract = open_bench_session(out_path, force=True)
    template_sync = sync_bench_session_template(out_path)
    template = dict(template_sync.get("template") or {})
    capture = filter_capture_for_template(golden, template)

    bench_result: Dict[str, Any]
    if not capture.get("measurements"):
        bench_result = {
            "ok": False,
            "error": "golden_capture_no_matching_gates",
            "template_gate_ids": [row.get("gate_id") for row in template.get("measurements") or []],
            "golden_gate_ids": [row.get("gate_id") for row in golden.get("measurements") or []],
        }
        after = bench_status(out_path)
    else:
        bench_result = submit_bench_capture(str(out_path), capture)
        after = (
            bench_result.get("bench_session")
            if isinstance(bench_result.get("bench_session"), dict)
            else bench_status(out_path)
        )

    drc_pass = bool(((build.get("build_compilation") or {}).get("design_quality") or {}).get("drc_pass"))
    simulated = bool(golden.get("simulated"))
    authority = _authority_summary(out_path)
    firmware_authorized = bool(authority.get("firmware_authorized"))
    contract_updates_ok = bool(contract_result.get("ok"))
    open_gates = [
        {
            "gate_id": gate.get("gate_id"),
            "gate_type": gate.get("gate_type"),
            "prompt": gate.get("prompt"),
            "interface_id": gate.get("interface_id"),
            "evidence_field": gate.get("evidence_field"),
            "critical": gate.get("critical"),
            "status": gate.get("status"),
        }
        for gate in (after.get("open_gates") or [])
        if isinstance(gate, Mapping)
    ]
    report = {
        "schema_version": SCHEMA,
        "ran_at": _now(),
        "out_dir": str(out_path),
        "build_id": build.get("build_id"),
        "drc_pass": drc_pass,
        "donor_vision_applied": int((build.get("donor_board_vision_report") or {}).get("applied_board_count") or 0),
        "golden_capture_path": str(Path(capture_path or DEFAULT_CAPTURE).resolve()),
        "golden_photo_path": str(DEFAULT_PHOTO) if DEFAULT_PHOTO.is_file() else None,
        "matched_measurement_count": capture.get("matched_gate_count"),
        "unmatched_measurement_count": len(capture.get("unmatched_measurements") or []),
        "simulated": simulated,
        "contract_update_count": len(contract_result.get("applied") or []),
        "contract_updates_ok": contract_updates_ok,
        "contract_updates": contract_result.get("applied") or [],
        "firmware_authorized": firmware_authorized,
        "authority": authority,
        "bench_before": {
            "readiness": before.get("readiness"),
            "open_gate_count": before.get("open_gate_count"),
            "critical_open_count": before.get("critical_open_count"),
            "power_on_authorized": before.get("power_on_authorized"),
        },
        "bench_after_contract": {
            "readiness": after_contract.get("readiness"),
            "open_gate_count": after_contract.get("open_gate_count"),
            "critical_open_count": after_contract.get("critical_open_count"),
            "power_on_authorized": after_contract.get("power_on_authorized"),
        },
        "bench_after": {
            "readiness": after.get("readiness"),
            "open_gate_count": after.get("open_gate_count"),
            "critical_open_count": after.get("critical_open_count"),
            "power_on_authorized": after.get("power_on_authorized"),
        },
        "open_gates": open_gates,
        "bench_submission_ok": bool(bench_result.get("ok")),
        "bench_submission_error": bench_result.get("error"),
        "passed": bool(
            drc_pass
            and contract_updates_ok
            and firmware_authorized
            and bench_result.get("ok")
            and after.get("power_on_authorized")
            and not simulated
        ),
    }
    report_path = out_path / "SPLICE_GOLDEN_REAL_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_path"] = str(report_path)
    return report
