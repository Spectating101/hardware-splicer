"""Rebuild the packaged SO-ARM102 follower drive reference from pinned upstream files."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote

from hardware_splicer.robot_model_import import parse_robot_model

REVISION = "43252799d077e7f9971d7c695fd59f31413aa9b6"
FILES = {
    "bom": ("docs/bom.md", "f598d19e82d4a6c5e46dfbf8532ef96a26864b97502ea23b0c0c8f9d7e97c8e9"),
    "assembly": ("docs/assembly-guide.md", "ef872fdb2d6aa76dead01399b3649673862d1f00f7c83254b62c048e8b1c948a"),
    "printing": ("docs/printing.md", "465fdab6f423d535756bff61c7a282a64ab025e2228d1c7e6ed3e98b11da126e"),
    "mount_step": ("models/step/common/SO102.02.070 Bottom arm.STEP", "efd21745accfefe30de56252ff63537ae3ef8b33137f8003c813b4fac57d8520"),
    "urdf": ("simulation/urdf/so_arm_102.urdf", "7ffcddec6eb9b54122bc9b8d612051464a6ba1a8580a53d5770f422e56fe5b63"),
    "cad_export": ("simulation/urdf/export_metadata.json", "23fa85e38094b55b471a61a2adc4512330c9ac7f980296638712b1fdf309af79"),
}


def build(root):
    content = {}
    sources = {}
    for key, (path, digest) in FILES.items():
        data = (root / path).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(f"Source differs from {REVISION}: {path}")
        content[key] = data
        sources[key] = {"url": f"https://github.com/roboninecom/SO-ARM102/blob/{REVISION}/{quote(path)}",
                        "sha256": digest}

    import cadquery as cq
    with TemporaryDirectory() as tmp:
        step = Path(tmp) / "mount.step"
        step.write_bytes(content["mount_step"])
        solids = cq.importers.importStep(str(step)).solids().vals()
        if len(solids) != 1 or not solids[0].isValid():
            raise ValueError("Expected one valid lower-arm solid")
        box = solids[0].BoundingBox()

    model = parse_robot_model(content["urdf"], "urdf")
    joints = {joint.name: joint for joint in model.joints}
    groups = {entry["motor_group"]: entry["link"] for entry in json.loads(content["cad_export"])["motor_groups"]}
    bom = content["bom"].decode()
    offer_row = next(line for line in bom.splitlines() if line.startswith("| STS3250 |"))
    drives = {}
    for key, name, servo_id, joint_name, long_cable in (
        ("shoulder", "Shoulder lift", 2, "link1_to_link2", [1, 2]),
        ("elbow", "Elbow flex", 3, "link2_to_link3", [3, 4]),
    ):
        row = next(line for line in bom.splitlines() if line.startswith(f"| {name} | {servo_id} |"))
        raw_mpn = row.split("|")[3].strip()
        joint = joints[joint_name]
        drives[key] = {
            "joint_name": name, "bus_id": servo_id, "mpn": raw_mpn.replace("С", "C"),
            "mpn_as_printed": raw_mpn, "manufacturer": "Feetech",
            "long_cable_bus_ids": long_cable, "long_cable_minimum_mm": 220,
            "motor_body_link": groups[servo_id],
            "simulation_joint": {"name": joint.name, "type": joint.joint_type.value,
                                 "parent": joint.parent_link_id, "child": joint.child_link_id,
                                 "travel_rad": [joint.limits["lower"], joint.limits["upper"]]},
        }

    return {
        "schema_version": "hardware_splicer.so102_follower_drives.v1",
        "project": "Robonine SO-ARM102 follower", "source_revision": REVISION, "sources": sources,
        "attribution": {"upstream": "roboninecom/SO-ARM102",
                        "source_licenses": f"https://github.com/roboninecom/SO-ARM102/blob/{REVISION}/LICENSING.md",
                        "adaptation": "HS selected two follower joints, summarized documentation and measured the lower-arm STEP."},
        "drives": drives, "supplier_offers_from_bom": re.findall(r"\]\((https://[^)]+)\)", offer_row),
        "wiring": {"supply_nominal_v": 12, "protocol": "Feetech TTL serial bus",
                   "controller": "Waveshare Bus Servo Adapter"},
        "mount": {"part_number": "SO102.02.070", "material": "PET-CF",
                  "step_solid_count": 1, "step_bounding_box_mm": [round(x, 3) for x in (box.xlen, box.ylen, box.zlen)],
                  "assembly_step": 6, "scope": "Shared by shoulder and elbow in one follower arm",
                  "step_quantities": {"lower_arm_print": 2, "M2x6_screw": 16, "short_cable": 2, "long_cable": 1},
                  "servo_horns": "One on each side of each servo"},
        "joint_mapping_basis": "HS maps the assembly IDs to the second and third revolute joints in kinematic chain order. Motor body links come from the CAD export.",
        "open_questions": ["Donor mounting-hole coordinates and horn spline fit",
                           "Connector contact numbering and polarity",
                           "Current margin with all follower loads operating",
                           "Continuous torque and thermal margin for the intended load",
                           "Condition and calibration of the individual servo"],
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source_root", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    report = build(args.source_root)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
