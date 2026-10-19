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
import re
import zipfile
from functools import partial
from typing import Any, Mapping

from .device_application import build_device_application
from .device_case import build_device_case
from .device_plan import DevicePlanError
from .mission_store import MissionError, MissionNotFound, MissionStateError, MissionStore, MissionValidationError, _normalize_author
from .intact_reuse import REPORT_SCHEMA as INTACT_REPORT_SCHEMA
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

    firmware_builder = partial(build_device_application, donor_modules=donor_modules) if donor_modules else build_device_application
    firmware, firmware_files = _deliverable(firmware_builder,
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
            "donors": sorted(donor_modules), "firmware_implemented": firmware["status"] == "generated",
            "firmware_scope": "proposed_passive_input_serial_monitor", "physical_correctness": "UNPROVEN"})
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


def _retained_manifest(data: bytes, view: Mapping[str, Any]) -> dict[str, Any] | None:
    """Recognize a hash-bound current prototype package; never generate a comparison package."""
    terminal = view.get("terminal") or {}
    if terminal.get("state") != "READY_FOR_HUMAN_BUILD":
        return None
    candidate = next((c for c in view["candidates"] if c["id"] == terminal.get("candidate_id")), None)
    if candidate is None:
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if (len(infos) > 4096 or len(set(names)) != len(names)
                    or sum(info.file_size for info in infos) > 64 * 1024 * 1024
                    or any(name.startswith("/") or "\\" in name or ".." in name.split("/") for name in names)
                    or any((info.external_attr >> 16) & 0o170000 == 0o120000 for info in infos)):
                return None
            manifest = json.loads(archive.read("MISSION_PACKAGE.json"))
            if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), dict):
                return None
            if (manifest.get("schema_version") != MISSION_PACKAGE_SCHEMA
                    or manifest.get("project_id") != view["project_id"]
                    or manifest.get("mission_id") != view["mission_id"]
                    or manifest.get("candidate_id") != candidate["id"]
                    or manifest.get("spec_sha256") != _sha(_canonical(candidate["spec"]))
                    or manifest.get("terminal") != {"state": terminal["state"], "grounding": terminal.get("grounding")}
                    or manifest.get("physical_correctness") != "UNPROVEN"
                    or manifest.get("firmware_authorized") is not False
                    or manifest.get("power_on_authorized") is not False
                    or not isinstance(manifest.get("deliverables"), dict)):
                return None
            if set(names) != set(manifest["files"]) | {"MISSION_PACKAGE.json"}:
                return None
            for name, entry in manifest["files"].items():
                content = archive.read(name)
                if (not isinstance(entry, dict) or entry.get("sha256") != _sha(content)
                        or entry.get("size_bytes") != len(content)):
                    return None
            terminal_seq = max(e["seq"] for e in view["events"] if e["type"] == "terminal_proposed")
            events = [e for e in view["events"] if e["seq"] <= terminal_seq]
            if (archive.read("02_design/spec.json") != _canonical(candidate["spec"])
                    or archive.read("01_requirements/intake.json") != _canonical(view["intake"])
                    or archive.read("06_provenance/events.jsonl") != b"".join(_canonical(e) + b"\n" for e in events)):
                return None
            base = candidate["evaluation_base_seq"]
            plan = _latest(candidate, "device_plan", base)
            review = _latest(candidate, "device_engineering", plan["seq"] if plan else base)
            if plan is None or review is None:
                return None
            for name, evaluation in (("02_design/plan.json", plan), ("02_design/engineering.json", review)):
                if _sha(archive.read(name)) != evaluation["result"]["result_sha256"]:
                    return None
            return manifest
    except (ValueError, KeyError, TypeError, OSError, zipfile.BadZipFile, RuntimeError):
        return None


def inspect_mission_delivery(missions: MissionStore, project_id: str, mission_id: str) -> dict[str, Any]:
    """Report retained output, not potential output. No builders, tests, or writes."""
    view = missions.get_mission(project_id, mission_id)
    base = f"/v1/projects/{project_id}/missions/{mission_id}"
    files = []
    for candidate in view["candidates"]:
        for evaluation in candidate["evaluations"]:
            artifact = evaluation.get("artifact")
            if not artifact:
                continue
            row = {"kind": "check_result", "candidate_id": candidate["id"], "operation": evaluation["operation"],
                   "evaluation_seq": evaluation["seq"], "current": evaluation["seq"] > candidate["evaluation_base_seq"],
                   "sha256": evaluation["result"]["result_sha256"], "presentation": "structured_data",
                   "status": "available", "download_path": f"{base}/{artifact}"}
            try:
                report = missions.read_run(project_id, mission_id, artifact)
            except (MissionError, OSError, ValueError):
                row.update(status="unavailable", download_path=None)
                files.append(row)
                continue
            files.append(row)
            if evaluation["operation"] != "intact_reuse" or report.get("software_checks_passed") is not True:
                continue
            bundle = {**row, "kind": "software_review_bundle", "scope": "SOFTWARE_REVIEW_ONLY",
                      "presentation": "software_review_zip", "sha256": report.get("package_sha256"),
                      "producer_attribution": "not_recorded", "download_path": f"{base}/{artifact}/bundle"}
            contract = report.get("contract") or {}
            try:
                if (report.get("schema_version") != INTACT_REPORT_SCHEMA
                        or contract.get("project_id") != project_id or contract.get("mission_id") != mission_id
                        or contract.get("candidate_id") != candidate["id"]
                        or missions.read_package(project_id, mission_id, report.get("package_sha256")) is None):
                    raise MissionStateError("software bundle is not bound to this mission")
            except (MissionError, OSError, ValueError, TypeError):
                bundle.update(status="unavailable", download_path=None)
            files.append(bundle)

    eligible = (view.get("terminal") or {}).get("state") == "READY_FOR_HUMAN_BUILD"
    packages = []
    status = "not_generated" if eligible else "blocked"
    scan_complete = True
    try:
        if eligible:
            for digest, data in missions.iter_retained_packages(project_id, mission_id):
                manifest = _retained_manifest(data, view)
                if manifest is not None:
                    packages.append({"sha256": digest, "size_bytes": len(data), "scope": "PROTOTYPE_REVIEW_ONLY",
                                     "producer_attribution": "not_recorded", "deliverables": manifest["deliverables"],
                                     "download_path": f"{base}/delivery/packages/{digest}"})
    except (MissionError, OSError):
        status, scan_complete = "unavailable", False
    if packages and scan_complete:
        status = "available"
    return {
        "schema_version": "hardware_splicer.mission_delivery_inspection.v1",
        "project_id": project_id, "mission_id": mission_id, "last_event_seq": view["last_event_seq"],
        "recorded_files": files,
        "prototype_package": {"status": status, "retained_packages": packages, "scan_complete": scan_complete,
                              "build_path": f"{base}/package" if eligible else None, "build_method": "POST" if eligible else None},
        "unresolved_needs": [n for n in view["needs"] if n["need_state"] != "resolved"],
        "safety_concerns": view["safety_concerns"], "physical_correctness": view["physical_correctness"],
        "sale_readiness": "NOT_ASSESSED", "inspection_generated_artifacts": False,
        "file_presence_proves_agent_delivery": False,
    }


def read_retained_mission_package(missions: MissionStore, project_id: str, mission_id: str, digest: str) -> bytes:
    """Download only an already-retained current package; unlike legacy GET /package, never build it."""
    if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise MissionValidationError("package hash must be 64 lowercase hex characters")
    view = missions.get_mission(project_id, mission_id)
    if (view.get("terminal") or {}).get("state") == "READY_FOR_HUMAN_BUILD":
        try:
            for stored_digest, data in missions.iter_retained_packages(project_id, mission_id):
                if stored_digest == digest and _retained_manifest(data, view) is not None:
                    return data
        except (MissionError, OSError) as exc:
            raise MissionStateError("retained package could not be verified") from exc
    raise MissionNotFound("no retained current prototype package with that hash")


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
            requires_verified_operator=True,
        )
        recorded = missions.record_design_staged(project_id, mission_id, review_id=review["review_id"],
                                                 package_sha256=package["package_sha256"])
        return dict(recorded["staged"])
