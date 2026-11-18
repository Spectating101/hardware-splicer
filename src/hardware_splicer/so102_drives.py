"""Inspect a source-linked follower drive and screen a proposed donor profile."""
from __future__ import annotations

import json
import math
from importlib.resources import files

from .part_substitution import PartProfile, evaluate_substitution


def follower_drive(joint: str, *, candidate: PartProfile | dict | None = None,
                   passive_leader: bool = False, angle_deg: float | None = None) -> dict:
    reference = files("hardware_splicer").joinpath("data/so102_follower_drives.json")
    report = json.loads(reference.read_text(encoding="utf-8"))
    drives = report.pop("drives")
    if joint not in drives:
        raise ValueError(f"Choose a follower joint from {', '.join(drives)}.")
    if passive_leader and candidate is not None:
        raise ValueError("Choose one donor profile.")
    drive = report["drive"] = drives[joint]
    if angle_deg is not None:
        if not math.isfinite(angle_deg):
            raise ValueError("Requested joint angle must be finite.")
        # The serialized radian limits round-trip whole-degree stops with sub-nanodegree error.
        lower, upper = [round(math.degrees(limit), 8) for limit in drive["simulation_joint"]["travel_rad"]]
        report["travel_check"] = {
            "requested_deg_from_urdf_zero": angle_deg,
            "model_range_deg": [lower, upper],
            "within_joint_limits": lower <= angle_deg <= upper,
            "scope": "Single joint position from CAD zero. Collision, torque and trajectory remain unassessed.",
        }
    rail_v = report["wiring"]["supply_nominal_v"]
    protocol = report["wiring"]["protocol"]
    source = {"source_id": "so102-bom", "content_hash": "sha256:" + report["sources"]["bom"]["sha256"],
              "pointer": f"Servos / {drive['joint_name']} / ID {drive['bus_id']}"}
    target = PartProfile(
        part_id=f"follower-{joint}", name=drive["joint_name"] + " servo", functions=["powered_joint_drive"],
        manufacturer=drive["manufacturer"], mpn=drive["mpn"], source=source,
        ports=[{"port_id": "power", "kind": "power", "direction": "input", "voltage_range_v": [rail_v, rail_v]},
               {"port_id": "bus", "kind": "signal", "direction": "bidirectional", "protocol": protocol}],
    )
    report["reference_profile"] = target.model_dump(mode="json", exclude_none=True)
    if passive_leader:
        candidate = PartProfile(part_id="passive-leader", name="Passive leader option without motor or gearbox",
                                manufacturer="Feetech", mpn="ST-3215-C066", functions=["joint_position_feedback"],
                                source={**source, "pointer": "Servos / Leader, 5V / passive option"})

    if candidate is not None:
        bus = PartProfile(
            part_id="follower-bus", name="Follower supply and adapter at the selected joint",
            ports=[{"port_id": "power", "kind": "power", "direction": "output", "voltage_range_v": [rail_v, rail_v]},
                   {"port_id": "bus", "kind": "signal", "direction": "bidirectional", "protocol": protocol}],
        )
        report["substitution"] = evaluate_substitution({
            "parts": [target, bus], "replace_part_id": target.part_id, "candidate": candidate,
            "connections": [{"connection_id": port.port_id, "from": {"part_id": bus.part_id, "port_id": port.port_id},
                             "to": {"part_id": target.part_id, "port_id": port.port_id}} for port in target.ports],
        })
        report["substitution_scope"] = "Selected drive on the nominal follower bus. Whole-arm current and mechanical fit remain open."
    return report
