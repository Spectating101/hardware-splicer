#!/usr/bin/env python3
"""Audit SORTCELL numerical trajectory with the official OpenArm collision meshes.

This runs real PyBullet collision detection and time parameterization. It does NOT
validate stage fixtures, v1.1 CAD registration, gripping, or real hardware safety.
All meshes, joints, limits, and coordinates originate from the same pinned v1.0
OpenArm URDF as the upstream kinematics artifact. No proxy robot geometry is used.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from scripts.solve_sortcell_openarm_pybullet_001 import (
    SCHEMA as INPUT_SCHEMA, URDF_REF, URDF_REPO, require, sha,
)

SCHEMA = "hardware_splicer.sortcell_openarm_collision_timing.v1"
RAW_SOURCE = "https://raw.githubusercontent.com/enactic/openarm_description/" + URDF_REF + "/"
PACKAGE = "package://openarm_description/"
# These are deliberately *engineering policy*, not manufacturer acceleration specs.
VELOCITY_FRACTION = 0.25
ACCELERATION_CAP_RAD_S2 = 1.5
ACCELERATION_CAP_M_S2 = 0.05
MIN_SEGMENT_S = 0.80


def source_meshes(root: ET.Element, asset_root: Path) -> list[dict]:
    meshes = set()
    for elem in root.findall(".//collision//mesh"):
        filename = elem.get("filename", "")
        require(filename.startswith(PACKAGE), "unrecognized non-source collision mesh: " + filename)
        relative = filename[len(PACKAGE):]
        require(".." not in Path(relative).parts and relative.endswith(".stl"),
                "non-source or unsafe collision mesh reference: " + relative)
        meshes.add(relative)
        # Only URI remapping; preserve original collision geometry, scale and origins.
        elem.set("filename", str(asset_root / relative))
    require(len(meshes) >= 10, "official collision mesh inventory unexpectedly small")
    return [{"upstream_path": name} for name in sorted(meshes)]


def fetch_source_meshes(meshes: list[dict], asset_root: Path) -> None:
    for item in meshes:
        path = item["upstream_path"]
        dest = asset_root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        url = RAW_SOURCE + quote(path, safe="/")
        with urlopen(Request(url, headers={"User-Agent": "hardware-splicer-source-collision-audit"}), timeout=45) as resp:
            blob = resp.read(50_000_001)
        require(84 <= len(blob) <= 50_000_000, "missing/oversized published mesh " + path)
        require(not blob.startswith(b"version https://git-lfs.github.com/spec/v1"),
                "upstream mesh returned LFS pointer, not real geometry: " + path)
        # STL can be ASCII (solid header) or binary; PyBullet is final geometry parser.
        dest.write_bytes(blob)
        item["bytes"] = len(blob)
        item["sha256"] = sha(blob)
        item["source_url"] = url


def select_policy_limit(info, p) -> tuple[float, float]:
    vel = float(info[11])  # PyBullet velocity limit from original URDF
    # PyBullet getJointInfo()[11] is maxVelocity; verify this is nonzero.
    require(math.isfinite(vel) and vel > 0, "source joint missing positive velocity limit")
    accel = ACCELERATION_CAP_M_S2 if info[2] == p.JOINT_PRISMATIC else ACCELERATION_CAP_RAD_S2
    return vel * VELOCITY_FRACTION, accel


def run(urdf: Path, trajectory: Path, output: Path) -> dict:
    import pybullet as p

    source = urdf.read_bytes()
    evidence = json.loads(trajectory.read_text())
    require(evidence.get("schema_version") == INPUT_SCHEMA, "kinematics receipt schema mismatch")
    require(evidence["official_urdf"]["commit"] == URDF_REF, "wrong source revision")
    require(evidence["official_urdf"]["sha256"] == sha(source), "trajectory and collision URDF differ")
    require(evidence["motion"]["robot_commands_authorized"] is False, "unexpected motion authority")
    require(evidence["motion"]["actual_robot_collision_meshes_loaded"] is False,
            "baseline kinematic artifact already purports to load collision geometry")

    output.mkdir(parents=True, exist_ok=True)
    require(not any(output.iterdir()), "output directory is not empty")
    root = ET.fromstring(source)
    require(root.tag == "robot" and root.get("name") == "openarm", "not original OpenArm robot")
    for link in root.findall("link"):
        for visual in link.findall("visual"):
            link.remove(visual)  # DAE visuals are not involved in physical collision checking.
    package_root = (output / "openarm_description").resolve()
    meshes = source_meshes(root, package_root)
    fetch_source_meshes(meshes, package_root)
    local = output / "openarm_v10_original_collision_geometry.urdf"
    local.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))

    client = p.connect(p.DIRECT)
    try:
        flags = (p.URDF_MAINTAIN_LINK_ORDER | p.URDF_USE_SELF_COLLISION |
                 p.URDF_USE_SELF_COLLISION_EXCLUDE_PARENT)
        body = p.loadURDF(str(local), useFixedBase=True, flags=flags, physicsClientId=client)
        nj = p.getNumJoints(body, physicsClientId=client)
        infos = [p.getJointInfo(body, j, physicsClientId=client) for j in range(nj)]
        movable = [(j, i) for j, i in enumerate(infos)
                   if i[2] in (p.JOINT_REVOLUTE, p.JOINT_PRISMATIC)]
        names = [i[1].decode() for _, i in movable]
        require(len(movable) == evidence["native_robot"]["movable_joint_count"],
                "joint count changed when source collision geometry loaded")
        require(len(movable) == 18, "unexpected original OpenArm moving-joint inventory")
        link_ids = {i[1].decode(): j for j, i in enumerate(infos)}
        tcp = link_ids["openarm_right_hand_tcp_joint"]
        shape_links = [link for link in range(-1, nj)
                       if p.getCollisionShapeData(body, link, physicsClientId=client)]
        require(len(shape_links) >= 14, "PyBullet did not load full original collision geometry")

        caps = {}
        for j, info in movable:
            name = info[1].decode()
            vel_cap, accel_cap = select_policy_limit(info, p)
            # URDF source velocities independently checked against XML, not an invented actuator model.
            src = root.find("./joint[@name='" + name + "']/limit")
            require(src is not None and abs(float(src.get("velocity")) - float(info[11])) < 1e-5,
                    "engine/source velocity limit mismatch: " + name)
            caps[name] = {
                "source_velocity_limit": float(src.get("velocity")),
                "policy_velocity_cap": vel_cap,
                "policy_acceleration_cap": accel_cap,
                "unit": "m" if info[2] == p.JOINT_PRISMATIC else "rad",
            }

        frames = evidence["trajectory"]
        segment_names = list(evidence["task"]["segments"])
        require(len(segment_names) == 7 and len(frames) >= 65, "missing full six-phase reference path")
        grouped = []
        for before, after in zip(segment_names[:-1], segment_names[1:]):
            key = before + "_TO_" + after
            group = [f for f in frames if f["segment"] == key]
            require(len(group) >= 8, "missing intermediate samples for " + key)
            grouped.append((key, group))
        require(sum(len(s) for _, s in grouped) == len(frames), "unaccounted trajectory frames")
        durations = []
        for n, (label, group) in enumerate(grouped):
            first = group[0]["joint_positions"]
            last = (grouped[n + 1][1][0] if n + 1 < len(grouped)
                    else group[-1])["joint_positions"]
            duration = MIN_SEGMENT_S
            for name in names:
                delta = abs(last[name] - first[name])
                cap = caps[name]
                duration = max(duration, 1.5 * delta / cap["policy_velocity_cap"],
                               math.sqrt(6 * delta / cap["policy_acceleration_cap"]))
            durations.append(round(duration * 1.02 + 0.00001, 7))

        t = 0.0
        measured = []
        contacts_by_pair = Counter()
        initial_contact_depths = None
        deepest_contact_depths = {}
        collision_samples = []
        actual_max_vel_ratio = 0.0
        actual_max_accel_ratio = 0.0
        max_fk_error_m = 0.0
        for segment_idx, ((label, group), duration) in enumerate(zip(grouped, durations)):
            first = group[0]["joint_positions"]
            last = (grouped[segment_idx + 1][1][0] if segment_idx + 1 < len(grouped)
                    else group[-1])["joint_positions"]
            for name in names:
                delta = abs(last[name] - first[name])
                cap = caps[name]
                v_ratio = 1.5 * delta / duration / cap["policy_velocity_cap"]
                a_ratio = 6 * delta / duration**2 / cap["policy_acceleration_cap"]
                actual_max_vel_ratio = max(actual_max_vel_ratio, v_ratio)
                actual_max_accel_ratio = max(actual_max_accel_ratio, a_ratio)
                require(v_ratio <= 1.00001 and a_ratio <= 1.00001,
                        "trajectory violates engineering speed/acceleration policy")
            denominator = len(group) if segment_idx < len(grouped) - 1 else len(group) - 1
            for index, frame in enumerate(group):
                local_t = index / denominator
                for j, info in movable:
                    p.resetJointState(body, j, float(frame["joint_positions"][info[1].decode()]),
                                      physicsClientId=client)
                p.performCollisionDetection(physicsClientId=client)
                actual = p.getLinkState(body, tcp, computeForwardKinematics=True,
                                        physicsClientId=client)[4]
                error = math.dist(actual, frame["tcp_position_m"])
                max_fk_error_m = max(max_fk_error_m, error)
                require(error < 0.00005, "collision model and reference model FK disagree")
                contacts = p.getContactPoints(bodyA=body, bodyB=body, physicsClientId=client)
                # Only source-mesh penetrations. Parent-child exclusions come from PyBullet flags.
                penetrations = [c for c in contacts if float(c[8]) < -1e-5]
                pair_depths = {}
                for c in penetrations:
                    pair = (min(c[3], c[4]), max(c[3], c[4]))
                    pair_depths[pair] = min(float(c[8]), pair_depths.get(pair, 0.0))
                pairs = sorted(pair_depths)
                if initial_contact_depths is None:
                    initial_contact_depths = dict(pair_depths)
                for pair in pairs:
                    contacts_by_pair[pair] += 1
                    deepest_contact_depths[pair] = min(
                        pair_depths[pair], deepest_contact_depths.get(pair, 0.0))
                if pairs:
                    collision_samples.append({"sample_index":frame["sample_index"],
                                              "segment":label,"pair_count":len(pairs),
                                              "deepest_penetration_m":round(min(c[8] for c in penetrations),7)})
                measured.append({
                    "sample_index":frame["sample_index"],
                    "segment":label,
                    "time_s":round(t + local_t * duration, 7),
                    "tcp_position_m":frame["tcp_position_m"],
                    "joint_positions":frame["joint_positions"],
                    "source_self_collision_penetration":bool(pairs),
                })
            t += duration
        require(len(measured) == len(frames) and measured[-1]["time_s"] > 0,
                "incomplete time-parameterized path")
        require(all(b["time_s"] > a["time_s"] for a, b in zip(measured, measured[1:])),
                "non-monotonic joint trajectory timestamps")
        found = [{"link_a":a, "link_b":b,
                  "joint_a": infos[a][12].decode() if a >= 0 else "base",
                  "joint_b": infos[b][12].decode() if b >= 0 else "base",
                  "frames":count,
                  "present_in_initial_pose":(a,b) in initial_contact_depths,
                  "initial_penetration_m":round(initial_contact_depths.get((a,b),0),7),
                  "deepest_path_penetration_m":round(deepest_contact_depths[(a,b)],7),
                  "additional_penetration_from_initial_m":round(max(
                      0, initial_contact_depths.get((a,b),0)-deepest_contact_depths[(a,b)]),7)}
                 for (a,b), count in contacts_by_pair.most_common()]
        # Note: getJointInfo()[12] is link name. Names are source-native.
        result = {
            "schema_version":SCHEMA,
            "input_schema":INPUT_SCHEMA,
            "official_urdf":{"repository":URDF_REPO, "commit":URDF_REF,
                             "sha256":hashlib.sha256(source).hexdigest()},
            "source_collision_geometry":{
                "official_stl_mesh_count":len(meshes),
                "loaded_link_collision_shape_count":len(shape_links),
                "meshes":meshes,
                "actual_source_collision_meshes_loaded":True,
                "self_collision_detection_enabled":True,
                "exclude_parent_link_collisions":True,
                "collision_detection_sample_count":len(measured),
                "penetrating_frame_count":len(collision_samples),
                "penetrating_link_pairs":found,
                "initial_pose_penetration_pair_count":len(initial_contact_depths),
                "persistent_all_sample_pair_count":sum(
                    1 for count in contacts_by_pair.values() if count==len(measured)),
                "new_pair_count_relative_to_initial_pose":len(
                    set(contacts_by_pair)-set(initial_contact_depths)),
                "increased_penetration_pair_count":sum(
                    1 for pair,depth in deepest_contact_depths.items()
                    if depth < initial_contact_depths.get(pair,0)-0.0001),
                "persistent_baseline_contact_is_not_exempted_as_safe":True,
                "penetrating_frames":collision_samples[:30],
                "original_robot_self_path_penetration_free":not bool(collision_samples),
                "workcell_fixture_collisions_audited":False,
                "object_and_gripper_contact_audited":False,
                "physical_clearance_certified":False,
            },
            "time_parameterization":{
                "source_urdf_velocity_limits_used":True,
                "velocity_fraction_of_source_limit":VELOCITY_FRACTION,
                "policy_acceleration_is_not_manufacturer_rated":True,
                "policy_acceleration_rad_s2":ACCELERATION_CAP_RAD_S2,
                "policy_acceleration_m_s2":ACCELERATION_CAP_M_S2,
                "segment_durations_s":dict(zip([x for x,_ in grouped],durations)),
                "total_duration_s":round(t,7),
                "max_analytic_velocity_fraction_of_policy":round(actual_max_vel_ratio,7),
                "max_analytic_acceleration_fraction_of_policy":round(actual_max_accel_ratio,7),
                "max_replayed_fk_residual_m":round(max_fk_error_m,8),
                "timed_samples":len(measured),
                "joint_policy_limits":caps,
                "motor_dynamics_or_torque_validated":False,
            },
            "authority":{
                "registered_to_v11_viewer":False,
                "calibrated_workcell_targets":False,
                "physical_grasp_verified":False,
                "collision_free_sorting_operation":False,
                "physical_motion_or_fabrication_authorized":False,
            },
            "timed_trajectory":measured,
        }
        (output / "OPENARM_SOURCE_COLLISION_AND_TIMING.json").write_text(
            json.dumps(result, indent=2) + "\n")
        (output / "SOURCE_COLLISION_SCOPE.md").write_text(
            "# SORTCELL OpenArm source collision and timing audit\n\n"
            "Full original OpenArm v1.0 collision STLs were loaded into PyBullet; "
            "the original source joint structure, collision mesh scales, inertial metadata "
            "and source velocity limits were retained. Only DAE visual meshes were omitted.\n\n"
            "Samples are rechecked against source-mesh forward kinematics and evaluated "
            "for source-robot self penetrations. Trajectory timestamps use manufacturer "
            "joint velocity limits at 25% plus a deliberately conservative, *non-manufacturer* "
            "engineering acceleration cap. They do NOT prove actuator tracking.\n\n"
            "This is **not** qualified workcell collision safety: no calibrated conveyor/tray "
            "meshes, payload, gripper forces, physical sensors, matched v1.1 visual CAD "
            "registration, or safety envelopes are validated. Any collision flags in the report "
            "must be repaired rather than ignored before a full sorting demonstration.\n")
        return result
    finally:
        p.disconnect(physicsClientId=client)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--urdf", required=True, type=Path)
    parser.add_argument("--trajectory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    receipt = run(args.urdf, args.trajectory, args.output)
    print(json.dumps({
        "original_collision_meshes":receipt["source_collision_geometry"]["official_stl_mesh_count"],
        "links_with_collision_shapes":receipt["source_collision_geometry"]["loaded_link_collision_shape_count"],
        "collision_samples":receipt["source_collision_geometry"]["collision_detection_sample_count"],
        "penetrating_frames":receipt["source_collision_geometry"]["penetrating_frame_count"],
        "initial_pair_count":receipt["source_collision_geometry"]["initial_pose_penetration_pair_count"],
        "new_pair_count":receipt["source_collision_geometry"]["new_pair_count_relative_to_initial_pose"],
        "deepening_pair_count":receipt["source_collision_geometry"]["increased_penetration_pair_count"],
        "duration_s":receipt["time_parameterization"]["total_duration_s"],
        "registered_to_viewer":receipt["authority"]["registered_to_v11_viewer"],
        "physical_authorization":receipt["authority"]["physical_motion_or_fabrication_authorized"],
    },indent=2))
