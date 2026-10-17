"""Read-only donor projections for mission events, never a contract writer.

Contracts live at projects/<project>/donors/contracts/donor__<board>__<block>.json.
Only the existing canonical physicalValidation envelope location is read. Neither
snapshot labels nor contract evidence IDs alone establish a measurement.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

from .donor.interface_contract import InterfaceContract, SCHEMA_VERSION
from .evidence_contract_store import _contract_from_dict
from .physical_evidence_ledger import PhysicalEvidenceEnvelope, validate_physical_evidence_envelope
from .project_store import ProjectStore, validate_project_id

_DONOR = re.compile(r"donor:[a-z0-9][a-z0-9-]{0,63}:[a-z0-9][a-z0-9-]{0,63}\Z")
_HASH = re.compile(r"[a-fA-F0-9]{64}\Z")
_METHODS = {"marking", "document", "firmware_analysis", "signal_capture", "vision", "continuity"}
_FACTS = ("voltage_max_v", "active_level", "controller_pin")
_GRADES = [None, "agent_assertion", "re_observation", "document", "person_measurement"]


def _text(value: Any, label: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{label} must be nonempty text of at most {limit} characters")
    if any(ord(c) < 32 and c not in "\n\t" for c in value) or any(0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise ValueError(f"{label} contains invalid characters")
    return value.strip()


def donor_id(value: Any) -> str:
    if not isinstance(value, str) or not _DONOR.fullmatch(value):
        raise ValueError("donor_id must be donor:<board>:<block> with lowercase alphanumeric/hyphen segments")
    return value


def normalize_donors(value: Any) -> list[dict]:
    if not isinstance(value, list) or len(value) > 40:
        raise ValueError("donors must be a list of at most 40 references")
    result = []
    seen = set()
    for row in value:
        if not isinstance(row, Mapping) or set(row) - {"donor_id", "label", "optional"}:
            raise ValueError("donors accept references only: donor_id, label, optional")
        ident = donor_id(row.get("donor_id"))
        if ident in seen:
            raise ValueError(f"duplicate donor reference: {ident}")
        seen.add(ident)
        optional = row.get("optional", False)
        if type(optional) is not bool:
            raise ValueError("donor.optional must be a boolean")
        result.append({"donor_id": ident, "label": _text(row.get("label"), "donor.label", 200), "optional": optional})
    return result


def normalize_used(value: Any, intake: list[Mapping] | None = None) -> list[str]:
    if not isinstance(value, list) or len(value) > 120:
        raise ValueError("donors_used must be a list of donor ids (at most 120 entries)")
    result = sorted({donor_id(v) for v in value})
    if intake is not None:
        extra = set(result) - {d["donor_id"] for d in intake}
        if extra:
            raise ValueError("donors_used not in intake: " + ", ".join(sorted(extra)))
    return result


def _inside_project(store: ProjectStore, project: str, parts: tuple[str, ...]) -> Path:
    root = store.root
    path = root
    for part in (validate_project_id(project), *parts):
        path = path / part
        if path.is_symlink():
            raise ValueError("donor contract path must not traverse symlinks")
    if not path.resolve().is_relative_to(root / project):
        raise ValueError("donor contract is outside its project")
    return path


def resolve_donor_contract(project_store: ProjectStore, project_id: str, ident: str) -> InterfaceContract | None:
    """Resolve only the named project-local contract; never write, follow links or search other projects."""
    ident = donor_id(ident)
    path = _inside_project(project_store, project_id, ("donors", "contracts", ident.replace(":", "__") + ".json"))
    if not path.exists():
        return None
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("donor contract exceeds 1 MiB")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("donor contract has an unsupported schema")
    for key in ("contacts", "signals", "power_domains"):
        rows = raw.get(key, [])
        if not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows):
            raise ValueError(f"donor contract contains malformed {key} rows")
    contract = _contract_from_dict(raw)
    if len(contract.contacts) != len(raw.get("contacts", [])) or len(contract.signals) != len(raw.get("signals", [])):
        raise ValueError("donor contract contains unnamed contacts or signals")
    if contract.virtual_module_id != ident or f"donor:{contract.board_id}:{contract.block_id}" != ident:
        raise ValueError("donor contract identity does not match its reference")
    if len({s.signal_id for s in contract.signals}) != len(contract.signals):
        raise ValueError("donor contract contains duplicate signals")
    if len({c.contact_id for c in contract.contacts}) != len(contract.contacts):
        raise ValueError("donor contract contains duplicate contacts")
    contract.recompute_status()  # Never trust the persisted status/firmware label.
    return contract


def _physical_records(store: ProjectStore, project: str, *, kind="electrical_measurement", snapshot=None) -> dict:
    snapshot = store.load(project)["snapshot"] if snapshot is None else snapshot
    validation = snapshot.get("physicalValidation") or {}
    audit = (validation.get("audited_physical_evidence") or {}) if isinstance(validation, Mapping) else {}
    envelopes = audit.get("envelopes") if isinstance(audit, Mapping) else None
    if not isinstance(envelopes, list):
        return {}
    records, seen = {}, set()
    for raw in envelopes:
        try:
            env = PhysicalEvidenceEnvelope.model_validate(raw)
        except (ValueError, TypeError):
            continue
        record = env.record
        ident = record.evidence_id
        if ident in seen:
            records.pop(ident, None)  # Duplicate identities are ambiguous, even if one copy is valid.
            continue
        seen.add(ident)
        if (validate_physical_evidence_envelope(env) or record.project_id != project
                or not record.passed or record.metadata.get("simulated")
                or record.kind.value != kind):
            continue
        records[ident] = record
    return records


def _fact(value, records: dict, ident: str) -> dict:
    raw = value.value
    if not (raw is None or type(raw) in (str, bool, int, float)) or (isinstance(raw, float) and not math.isfinite(raw)):
        raise ValueError("donor fact values must be finite JSON scalars")
    state, review = value.status.value, value.review_status.value
    grade = {"observed": "re_observation", "reference_only": "document",
             "inferred": "agent_assertion", "assumed": "agent_assertion", "measured": "agent_assertion"}.get(state)
    if (state == "measured" and review == "accepted" and value.evidence_ids and raw is not None
            and all(ref in records and ident in records[ref].target_ids for ref in value.evidence_ids)):
        grade = "person_measurement"
    return {"value": raw, "unit": value.unit, "epistemic_state": state, "review_state": review,
            "evidence_ids": list(value.evidence_ids), "grade": grade}


def read_donors(store: ProjectStore, project: str, references: list[Mapping]) -> list[dict]:
    snapshot = store.load(project)["snapshot"]
    records = _physical_records(store, project, snapshot=snapshot)
    dimensions = _physical_records(store, project, snapshot=snapshot, kind="dimensional_measurement")
    result = []
    for ref in references:
        ident = ref["donor_id"]
        contract = resolve_donor_contract(store, project, ident)
        row = {**ref, "contract_state": "unknown", "can_generate_firmware": False, "signals": [],
               "capabilities": [], "missing_facts": ["contract"]}
        if contract:
            row["has_power_domains"] = bool(contract.power_domains)
            missing, grades, signals = [], [], []
            contact_ids = {c.contact_id for c in contract.contacts}
            for s in contract.signals:
                facts = {f: _fact(getattr(s, f), records, ident) for f in _FACTS}
                active = s.direction.value in {"input", "output", "bidirectional"}
                required = _FACTS if active else ("voltage_max_v",)
                for f in required:
                    grades.append(facts[f]["grade"])
                    if facts[f]["grade"] != "person_measurement":
                        missing.append(f"signals.{s.signal_id}.{f}")
                if s.direction.value == "unknown":
                    missing.append(f"signals.{s.signal_id}.direction")
                    grades.append(None)
                if s.contact_id not in contact_ids:
                    missing.append(f"signals.{s.signal_id}.contact")
                    grades.append(None)
                signals.append({"name": s.signal_id, "contact_id": s.contact_id, "direction": s.direction.value,
                                "protocol": _fact(s.protocol, records, ident), **facts})
            complete = _fact(contract.interface_complete, records, ident)
            grades.append(complete["grade"])
            if complete["grade"] != "person_measurement" or complete["value"] is not True:
                missing.append("interface_complete")
            if not contract.contacts:
                missing.append("contacts")
                grades.append(None)
            if not contract.signals:
                missing.append("signals")
                grades.append(None)
            if contract.blockers:
                grades.append(None)
            state = contract.recompute_status().value
            if state == "verified" and missing:
                state = "partial"
            row.update(contract_state=state, can_generate_firmware=not missing and contract.can_generate_firmware(),
                       signals=signals, interface_complete=complete, missing_facts=missing + list(contract.blockers),
                       capabilities=[{"role": contract.functional_role,
                           "grade": min(grades, key=_GRADES.index) if grades else None}])
            if contract.planner_geometry.value is not None:
                geometry = _fact(replace(contract.planner_geometry, value=True), dimensions, ident)
                geometry["value"] = json.loads(json.dumps(contract.planner_geometry.value, allow_nan=False))
                row["planner_geometry"] = geometry
        result.append(row)
    return result


def normalize_finding(value: Any, references: list[Mapping]) -> dict:
    keys = {"donor_id", "signal", "claim", "method", "artifacts", "source"}
    if not isinstance(value, Mapping) or set(value) - keys:
        raise ValueError("finding accepts only donor_id, signal, claim, method, artifacts, source")
    ident = donor_id(value.get("donor_id"))
    if ident not in {r["donor_id"] for r in references}:
        raise ValueError("finding donor must be in intake")
    method = value.get("method")
    if not isinstance(method, str) or method not in _METHODS:
        raise ValueError("finding.method is not supported")
    artifacts = value.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) > 20:
        raise ValueError("finding.artifacts must contain at most 20 hash references")
    normalized = []
    for artifact in artifacts:
        if not isinstance(artifact, Mapping) or set(artifact) != {"name", "sha256"}:
            raise ValueError("artifact accepts only name and sha256")
        digest = artifact["sha256"]
        if not isinstance(digest, str) or not _HASH.fullmatch(digest):
            raise ValueError("artifact.sha256 must contain 64 hex characters")
        normalized.append({"name": _text(artifact["name"], "artifact.name", 200), "sha256": digest.lower()})
    return {"donor_id": ident, "signal": _text(value["signal"], "finding.signal", 120) if value.get("signal") is not None else None,
            "claim": _text(value.get("claim"), "finding.claim", 4000), "method": method,
            "source": _text(value.get("source"), "finding.source", 200), "artifacts": normalized,
            "grade": "re_observation"}


def donor_problem(replayed: Mapping, spec: Mapping, *, ready: bool) -> str | None:
    used = set(spec.get("donors_used") or [])
    references = replayed.get("donor_references") or []
    missing = [r["donor_id"] for r in references if not r["optional"] and r["donor_id"] not in used]
    if missing:
        return "required donors not covered: " + ", ".join(missing)
    if ready:
        by_id = {d["donor_id"]: d for d in replayed.get("donors") or []}
        for ident in sorted(used):
            donor = by_id.get(ident)
            if not donor or donor["contract_state"] != "verified":
                return f"donor {ident} is not verified; missing facts: " + ", ".join(donor["missing_facts"] if donor else ["donor_read"])
    return None


def donor_grounding(replayed: Mapping, events: list[Mapping], terminal: Mapping, cites: list[int]) -> str:
    donors = {d["donor_id"]: d for d in replayed.get("donors") or []}
    candidates = replayed["candidates"]
    for event in events:
        if event["seq"] not in cites or event["type"] != "evidence_required" or event["blocker"] != terminal["state"]:
            continue
        candidate = terminal.get("candidate_id")
        if event.get("candidate_id") not in (None, candidate):
            continue
        request = event.get("request") or {}
        donor = donors.get(request.get("target"))
        if not donor:
            continue
        name = request.get("signal")
        signal = next((s for s in donor["signals"] if s["name"] == name), None)
        if terminal["state"] == "BLOCKED_NEEDS_REVERSE_ENGINEERING":
            if donor["contract_state"] == "unknown" or (signal and any(signal[f]["epistemic_state"] == "unknown" for f in _FACTS)):
                return "hs_donor_reading"
        elif terminal["state"] == "BLOCKED_NEEDS_PHYSICAL_MEASUREMENT" and signal and candidate in candidates:
            if donor["donor_id"] not in candidates[candidate]["spec"].get("donors_used", []):
                continue
            measured = any(m["signal"] == name for m in donor.get("person_measurements", []))
            if request.get("kind") == "electrical" and not measured and any(signal[f]["grade"] != "person_measurement" for f in _FACTS):
                return "hs_donor_contract"
    return "agent_assertion"
