"""Evidence intake for one physical RC donor, using HS bench_topology_capture.v1.

Operator-entered readings are provenance-linked *claims*. This layer never
runs instruments, trusts simulated captures, certifies a component, or closes
any physical build/power-on/motor-motion authority on its own.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from .bench_capture_bridge import collect_capture_measurements, extract_bench_capture

SCHEMA = "hardware_splicer.donor_characterization.v1"
CAPTURE = "bench_topology_capture.v1"
MAX_BYTES = 3_000_000
# Cross-domain geometry, electrical behavior, and photos are distinct evidence
# categories. Stall-current tests are NOT requested by this generic intake.
FIELDS = {
    "battery_open_circuit_v": ("V", "electrical", 0.1, 60.0),
    "motor_left_winding_ohm": ("ohm", "electrical", 0.01, 10000.0),
    "motor_right_winding_ohm": ("ohm", "electrical", 0.01, 10000.0),
    "motor_left_no_load_current_a": ("A", "electrical", 0.001, 20.0),
    "motor_right_no_load_current_a": ("A", "electrical", 0.001, 20.0),
    "motor_left_test_voltage_v": ("V", "electrical", 0.1, 24.0),
    "motor_right_test_voltage_v": ("V", "electrical", 0.1, 24.0),
    "wheel_left_diameter_mm": ("mm", "mechanical", 1.0, 500.0),
    "wheel_right_diameter_mm": ("mm", "mechanical", 1.0, 500.0),
    "axle_spacing_mm": ("mm", "mechanical", 1.0, 1000.0),
    "chassis_length_mm": ("mm", "mechanical", 1.0, 2000.0),
    "chassis_width_mm": ("mm", "mechanical", 1.0, 2000.0),
}
VALID_INSTRUMENT_STATUS = frozenset({"valid", "calibrated", "in_calibration", "current"})
ACCEPTED_ROW_STATUS = frozenset({"pass", "passed", "measured", "ok"})
VALID_REVIEW_SOURCE = "physical_donor_operator_report"


def _digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _load(source: str | Path) -> tuple[dict, str]:
    path = Path(source)
    if not path.is_file() or path.is_symlink() or not 0 < path.stat().st_size <= MAX_BYTES:
        raise ValueError("capture is missing, symlinked or oversized")
    raw = path.read_bytes()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("capture must be a JSON object")
    return data, _digest(raw)


def create_donor_capture_template(*, intake_sha256: str, fixture_sha256: str,
                                  donor_board_id: str = "donor_rc_car_ctrl") -> dict:
    if not (intake_sha256.startswith("sha256:") and fixture_sha256.startswith("sha256:")):
        raise ValueError("donor template requires source fingerprints")
    return {
        "schema_version": CAPTURE,
        "capture_id": None,
        "project_name": "robot_drive_from_rc_toy",
        "build_id": "robot_drive_base",
        "donor_characterization": {
            "schema": SCHEMA,
            "intake_sha256": intake_sha256,
            "fixture_sha256": fixture_sha256,
            "donor_board_id": donor_board_id,
            "physical_donor_id": None,
            "source_kind": VALID_REVIEW_SOURCE,
        },
        "operator_id": None,
        "recorded_at": None,
        "simulated": None,
        "instruments": [],
        "measurements": [
            {"measurement_id": key, "unit": unit, "value": None,
             "status": "open", "instrument_id": None, "notes": "",
             "evidence_uri": None}
            for key,(unit,_,_,_) in FIELDS.items()
        ],
        "artifacts": [
            {"kind": "donor_identification_photo", "uri": None,
             "sha256": None, "actual_donor_id_visible": False},
            {"kind": "instrument_log", "uri": None, "sha256": None,
             "actual_donor_id_visible": False},
        ],
        "policy": {
            "measurements_must_be_from_this_physical_donor": True,
            "no_live_battery_to_underrated_motor": True,
            "do_not_attempt_uncontrolled_stall_current_test": True,
            "motor_power_on_requires_independent_electrical_review": True,
            "operator_report_is_not_independently_verified": True,
            "template_does_not_close_release_gates": True,
        },
    }


def evaluate_donor_capture(*, capture_path: str | Path,
                           intake_sha256: str, fixture_sha256: str,
                           board_id: str = "donor_rc_car_ctrl") -> dict:
    packet, source_sha = _load(capture_path)
    capture = extract_bench_capture(packet)
    if not capture or capture.get("schema_version") != CAPTURE:
        raise ValueError("capture must use existing bench_topology_capture.v1 schema")
    binding = capture.get("donor_characterization")
    if not isinstance(binding, Mapping) or binding.get("schema") != SCHEMA:
        raise ValueError("missing characterization binding")
    if (binding.get("intake_sha256") != intake_sha256
            or binding.get("fixture_sha256") != fixture_sha256
            or binding.get("donor_board_id") != board_id):
        raise ValueError("physical donor capture source binding differs from intake/fixture")
    if binding.get("source_kind") != VALID_REVIEW_SOURCE:
        raise ValueError("capture cannot impersonate a physical donor")
    physical_id = binding.get("physical_donor_id")
    if not isinstance(physical_id, str) or not physical_id.strip() or len(physical_id)>100:
        raise ValueError("identify the specific physical donor, not a generic fixture")
    if capture.get("simulated") is not False:
        raise ValueError("simulated or unclassified bench captures cannot upgrade a real donor")
    operator = capture.get("operator_id")
    if not isinstance(operator,str) or not operator.strip():
        raise ValueError("actual operator identity required")
    when = capture.get("recorded_at")
    if not isinstance(when,str):
        raise ValueError("capture requires an offset-aware recorded_at")
    try:
        parsed = datetime.fromisoformat(when.replace("Z","+00:00"))
    except ValueError as exc:
        raise ValueError("invalid recorded_at") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("capture timestamp must specify timezone")

    instruments = capture.get("instruments")
    if not isinstance(instruments,list) or len(instruments)>25:
        raise ValueError("bounded instrument registry required")
    ids = [x.get("instrument_id") for x in instruments if isinstance(x,Mapping)]
    if (len(ids)!=len(instruments)
            or any(not isinstance(x,str) or not x for x in ids)
            or len(ids)!=len(set(ids))):
        raise ValueError("invalid or ambiguous instrument identities")
    instrument_index = {x["instrument_id"]:x for x in instruments}
    rows = collect_capture_measurements(capture)
    if len(rows)>64:
        raise ValueError("too many donor measurement rows")
    seen:set[str]=set()
    accepted = {}
    quarantined = []
    for row in rows:
        if not isinstance(row,Mapping):
            raise ValueError("invalid measurement structure")
        field = row.get("measurement_id")
        if field not in FIELDS or field in seen:
            raise ValueError("unknown or duplicate donor measurement identity")
        seen.add(field)
        unit, category, lo, hi = FIELDS[field]
        if row.get("status") not in ACCEPTED_ROW_STATUS:
            if row.get("status") not in ("open","pending","fail","blocked"):
                raise ValueError("unrecognized donor measurement status")
            continue
        if row.get("unit") != unit:
            raise ValueError(f"{field}: physical unit mismatch")
        v = row.get("value")
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):
            raise ValueError(f"{field}: nonfinite or nonnumeric measurement")
        if not lo <= v <= hi:
            raise ValueError(f"{field}: physically implausible measurement")
        instrument = instrument_index.get(row.get("instrument_id"))
        if not instrument or instrument.get("calibration_status") not in VALID_INSTRUMENT_STATUS:
            quarantined.append({"measurement_id":field, "reason":"instrument_provenance_not_qualified"})
            continue
        if row.get("simulated") is True:
            quarantined.append({"measurement_id":field, "reason":"synthetic_measurement"})
            continue
        accepted[field] = {
            "value":float(v),"unit":unit,"domain":category,
            "instrument_id":instrument["instrument_id"],
            "authority":"operator_reported_instrument_reading_not_independently_verified",
        }
    # A source photo/measurement log is traceable only when the operator
    # provided a URI plus a SHA-256 checksum. Merely naming it is inadequate.
    artifacts = capture.get("artifacts") or []
    if not isinstance(artifacts,list) or len(artifacts)>25:
        raise ValueError("invalid attached provenance")
    traceable=[]
    for a in artifacts:
        if not isinstance(a,Mapping):
            raise ValueError("invalid provenance artifact")
        sha=a.get("sha256")
        if (isinstance(a.get("uri"),str) and a["uri"].strip()
                and isinstance(sha,str) and len(sha)==71
                and sha.startswith("sha256:")
                and all(c in "0123456789abcdef" for c in sha[7:])):
            traceable.append({"kind":a.get("kind"),
                              "uri":a["uri"],"sha256":sha})
    observations = {key:item["value"] for key,item in accepted.items()}
    paired=("motor_left_winding_ohm","motor_right_winding_ohm")
    conflicts=[]
    if all(k in observations for k in paired):
        resist=[observations[k] for k in paired]
        ratio=max(resist)/min(resist)
        if ratio>1.5:
            conflicts.append({"id":"motor_winding_mismatch",
                              "ratio":round(ratio,4),
                              "action":"quarantine motor pair pending investigation"})
    if all(x in observations for x in ("motor_left_test_voltage_v","motor_right_test_voltage_v")):
        for ref in ("left","right"):
            if observations[f"motor_{ref}_test_voltage_v"]>6.0:
                conflicts.append({"id":f"motor_{ref}_overvoltage",
                                  "action":"do not rely on test: declared motor rating 6 V"})
    if "battery_open_circuit_v" in observations and observations["battery_open_circuit_v"]>6.0:
        conflicts.append({"id":"battery_exceeds_declared_motor_rating",
                          "action":"never route battery directly to donor 6 V motors"})
    readiness = ("measured_inputs_with_conflicts_review_required" if conflicts
                 else "partial_instrument_readings_review_required" if accepted
                 else "no_qualified_instrument_readings")
    return {
        "schema":SCHEMA,
        "status":readiness,
        "source_capture_sha256":source_sha,
        "bound_intake_sha256":intake_sha256,
        "bound_fixture_sha256":fixture_sha256,
        "donor_board_id":board_id,
        "physical_donor_id":physical_id,
        "operator_id":operator,
        "instrument_provenance_claimed":bool(accepted),
        "input_fields_expected":len(FIELDS),
        "input_fields_observed":len(accepted),
        "instruments_declared":len(instruments),
        "accepted_readings":accepted,
        "unqualified_readings":quarantined,
        "source_attestations":traceable,
        "conflicts":conflicts,
        "all_measurement_evidence_independently_authenticated":False,
        "physical_donor_fully_characterized":False,
        "independent_motor_driver_spec_qualified":False,
        "motor_motion_authorized":False,
        "power_on_authorized":False,
        "fabrication_authorized":False,
        "release_authorized":False,
    }
