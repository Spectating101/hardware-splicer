"""What a READY mission hands a person: one package to build from, and its design staged for their review.

READY_FOR_HUMAN_BUILD says HS's software checks support the candidate. The package carries the accepted intake, the
design and the exact run files READY rests on, the firmware and enclosure HS can generate, every software check it
recorded, and the physical checks that remain. A deliverable HS cannot generate is named as blocked. Nothing in it
claims physical truth.

Staging opens a project review holding the design and the repairs that produced it. A review is not a revision: only
a person's decision through the existing review workflow promotes it. The mission never decides it.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import zipfile
from functools import partial
from typing import Any, Mapping

from .device_application import build_device_application
from .device_case import build_device_case
from .device_plan import DevicePlanError
from .mission_store import MissionStateError, MissionStore, _normalize_author
from .project_review_store import ProjectReviewStore
from .donor_device_plan import mission_donor_modules

MISSION_PACKAGE_SCHEMA = "hardware_splicer.mission_package.v1"
_ZIP_DATE = (1980, 1, 1, 0, 0, 0)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _ready(missions: MissionStore, project_id: str, mission_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    view = missions.get_mission(project_id, mission_id)
    terminal = view.get("terminal") or {}
    if terminal.get("state") != "READY_FOR_HUMAN_BUILD":
        raise MissionStateError("only a mission that reached READY_FOR_HUMAN_BUILD has a package")
    candidate = next(c for c in view["candidates"] if c["id"] == terminal["candidate_id"])
    return view, candidate


def _since_latest_repair(view: Mapping[str, Any], candidate: Mapping[str, Any]) -> int:
    repairs = [e["seq"] for e in view["events"] if e["type"] == "repair_proposed" and e["candidate_id"] == candidate["id"]]
    proposed = next(e["seq"] for e in view["events"]
                    if e["type"] == "candidate_proposed" and e["candidate"]["id"] == candidate["id"])
    return max(repairs) if repairs else proposed


def _latest(candidate: Mapping[str, Any], operation: str, after_seq: int) -> dict[str, Any] | None:
    found = [e for e in candidate["evaluations"] if e["operation"] == operation and e["seq"] > after_seq]
    return found[-1] if found else None


def _unzip(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {name: archive.read(name) for name in archive.namelist() if not name.endswith("/")}


def _deliverable(builder, spec: Mapping[str, Any], folder: str, what: str) -> tuple[dict[str, Any], dict[str, bytes]]:
    try:
        _metadata, package = builder(copy.deepcopy(dict(spec)))
    except DevicePlanError as exc:
        reason = str(exc)
        text = (f"# {what}: not generated\n\nHardware Splicer could not generate the {what.lower()} for this design:\n\n"
                f"{reason}\n\nThis is a limit of what HS generates, not a finding about the design.\n")
        return {"status": "blocked", "reason": reason}, {f"{folder}/BLOCKED.md": text.encode("utf-8")}
    return {"status": "generated"}, {f"{folder}/{name}": data for name, data in _unzip(package).items()}


def _firmware_test(candidate: Mapping[str, Any], after_seq: int) -> dict[str, Any]:
    run = _latest(candidate, "device_application_run", after_seq)
    if run is None:
        return {"status": "not_run",
                "note": "No off-hardware run of the application was recorded for this design."}
    errors, warnings = int(run["result"].get("errors") or 0), int(run["result"].get("warnings") or 0)
    status = "modeled_passed" if errors == 0 and warnings == 0 else "modeled_partial" if errors == 0 else "modeled_failed"
    return {"status": status, "evaluation_seq": run["seq"], "summary": run["result"].get("summary", ""),
            "note": "A host model of the application logic, not a test on hardware."}


def _checklist(checks: list[str]) -> bytes:
    lines = ["# Physical checks still required", "",
             "Hardware Splicer's checks are software checks. None of these has been done, and nothing in this package "
             "authorizes powering, flashing or using the device.", ""]
    lines += [f"- [ ] {check}" for check in checks]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _assemble(missions: MissionStore, project_id: str, mission_id: str) -> tuple[dict[str, Any], bytes]:
    view, candidate = _ready(missions, project_id, mission_id)
    spec = candidate["spec"]
    donor_modules = mission_donor_modules(view, spec)
    since = _since_latest_repair(view, candidate)
    plan_eval = _latest(candidate, "device_plan", since)
    review_eval = _latest(candidate, "device_engineering", plan_eval["seq"] if plan_eval else since)
    if plan_eval is None or review_eval is None:
        raise MissionStateError("READY_FOR_HUMAN_BUILD rests on a device_plan and a device_engineering evaluation")
    # The package describes the mission up to its verdict. Delivery events after READY (staging) never change it.
    terminal_seq = max(e["seq"] for e in view["events"] if e["type"] == "terminal_proposed")
    events = [e for e in view["events"] if e["seq"] <= terminal_seq]
    by_type = {e["type"]: e for e in events if e["type"] in {"accepted", "inventory_read"}}
    checks = list(view["terminal"].get("physical_evidence_required") or [])

    def donor_firmware(_spec):
        raise DevicePlanError("Donor firmware is not implemented; a library-only application would omit donor behavior")
    firmware, firmware_files = _deliverable(donor_firmware if donor_modules else build_device_application,
                                           spec, "03_firmware", "Firmware")
    case_builder = partial(build_device_case, donor_modules=donor_modules) if donor_modules else build_device_case
    enclosure, enclosure_files = _deliverable(case_builder, spec, "04_enclosure", "Enclosure")
    files: dict[str, bytes] = {
        "01_requirements/intake.json": _canonical(view["intake"]),
        "01_requirements/accepted.json": _canonical(by_type.get("accepted")),
        "01_requirements/inventory_read.json": _canonical(by_type.get("inventory_read")),
        "02_design/spec.json": _canonical(spec),
        "02_design/plan.json": missions.read_run_bytes(project_id, mission_id, plan_eval["artifact"]),
        "02_design/engineering.json": missions.read_run_bytes(project_id, mission_id, review_eval["artifact"]),
        **firmware_files,
        **enclosure_files,
        "05_validation/software_checks.json": _canonical([
            {"operation": e["operation"], "seq": e["seq"], "result": e["result"], "artifact": e["artifact"]}
            for e in candidate["evaluations"]
        ]),
        "05_validation/physical_checks_required.md": _checklist(checks),
        "06_provenance/events.jsonl": b"".join(_canonical(e) + b"\n" for e in events),
    }
    if donor_modules:
        files["01_requirements/donor_read.json"] = _canonical(next(e for e in events if e["type"] == "donor_read"))
        files["02_design/donor_scope.json"] = _canonical({"implementation": "passive_switch_topology_and_geometry",
            "donors": sorted(donor_modules), "firmware_implemented": False, "physical_correctness": "UNPROVEN"})
    manifest = {
        "schema_version": MISSION_PACKAGE_SCHEMA,
        "project_id": project_id,
        "mission_id": mission_id,
        "candidate_id": candidate["id"],
        "terminal": {"state": view["terminal"]["state"], "grounding": view["terminal"].get("grounding")},
        "spec_sha256": _sha(_canonical(spec)),
        "files": {name: {"sha256": _sha(data), "size_bytes": len(data)} for name, data in sorted(files.items())},
        "deliverables": {
            "firmware": firmware,
            "firmware_test": _firmware_test(candidate, since),
            "enclosure": enclosure,
            "physical": {"status": "required", "checks": checks},
        },
        "physical_correctness": "UNPROVEN",
        "firmware_authorized": False,
        "power_on_authorized": False,
    }
    files["MISSION_PACKAGE.json"] = _canonical(manifest)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=_ZIP_DATE)
            info.external_attr = 0o644 << 16
            archive.writestr(info, files[name])
    return manifest, output.getvalue()


def build_mission_package(missions: MissionStore, project_id: str, mission_id: str) -> dict[str, Any]:
    """Build (or find) the READY mission's package. Deterministic: the same mission gives the same bytes."""

    manifest, data = _assemble(missions, project_id, mission_id)
    digest = missions.store_package(project_id, mission_id, data)
    return {**manifest, "package_sha256": digest}


def read_mission_package(missions: MissionStore, project_id: str, mission_id: str) -> bytes:
    digest = build_mission_package(missions, project_id, mission_id)["package_sha256"]
    data = missions.read_package(project_id, mission_id, digest)
    if data is None:
        raise MissionStateError("the package was not stored")
    return data


def _repairs(view: Mapping[str, Any], candidate_id: str) -> list[dict[str, Any]]:
    chain = []
    last_plan_seq = None
    for event in view["events"]:
        if (event["type"] == "evaluation_recorded" and event.get("candidate_id") == candidate_id
                and event.get("operation") == "device_plan"):
            last_plan_seq = event["seq"]
        elif event["type"] == "repair_proposed" and event["candidate_id"] == candidate_id:
            chain.append({"seq": event["seq"], "rationale": event["rationale"],
                          "spec_sha256": _sha(_canonical(event["spec"])), "after_evaluation_seq": last_plan_seq})
    return chain


def stage_mission_design(missions: MissionStore, project_id: str, mission_id: str, *, author: Mapping[str, Any]) -> dict[str, Any]:
    """Open a review of the READY design, once. Promoting it stays a person's review decision."""

    _normalize_author(author)
    # Under the mission lock, so two stagings cannot both open a review.
    with missions.mutation(project_id, mission_id):
        view, candidate = _ready(missions, project_id, mission_id)
        if view.get("staged"):
            return dict(view["staged"])
        package = build_mission_package(missions, project_id, mission_id)
        projects = missions.project_store
        latest = projects.load_latest_with_recovery(project_id)
        snapshot = copy.deepcopy(latest["snapshot"])
        designs = dict(snapshot.get("deviceDesigns") or {})
        designs[mission_id] = {
            "candidate_id": candidate["id"],
            "spec": copy.deepcopy(candidate["spec"]),
            "package_sha256": package["package_sha256"],
            "terminal": {key: view["terminal"].get(key) for key in ("state", "reason", "cites", "grounding")},
            "evaluations": [{"operation": e["operation"], "seq": e["seq"], "result_sha256": e["result"].get("result_sha256")}
                            for e in candidate["evaluations"]],
            "repairs": _repairs(view, candidate["id"]),
            "physical_correctness": "UNPROVEN",
        }
        snapshot["deviceDesigns"] = designs
        author_id = _normalize_author(author)["id"]  # an agent or person; never Hardware Splicer itself
        review = ProjectReviewStore(projects).create(
            project_id, snapshot, base_revision=int(latest["revision"]), created_by=author_id,
            note=f"Design from fabrication mission {mission_id} (READY_FOR_HUMAN_BUILD). A person decides this review.",
        )
        recorded = missions.record_design_staged(project_id, mission_id, review_id=review["review_id"],
                                                 package_sha256=package["package_sha256"])
        return dict(recorded["staged"])
