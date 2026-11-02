#!/usr/bin/env python3
"""Independent numerical acceptance gate for SORTCELL source-PyBullet cycle.

Does not execute dynamics or manufacture a passing result. Verifies the
serialized output of the original manufacturer-URDF PyBullet contact run.
This is NOT a robot safety or real hardware certification.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path

EXPECTED_PHASES=(
 "settle_open_gripper",
 "grasp_close_source_fingers",
 "lift_under_gravity",
 "raise_to_source_fk_clearance",
 "source_fk_clearance_transfer",
 "lower_to_proposed_sort_station",
 "release_open_source_fingers",
 "reset_robot_without_object_attachment",
)


def verify(path:Path,urdf:Path)->dict:
    data=json.loads(path.read_text())
    motion=data["cycle"]
    layout=data["candidate_layout"]
    authority=data["workpiece"]
    assert data["schema_version"]=="hardware_splicer.sortcell_source_robot_pick_place_candidate.v1"
    assert data["original_urdf_sha256"]==hashlib.sha256(urdf.read_bytes()).hexdigest()
    assert data["source_collision_meshes"]>=11 and data["openarm_original_joint_count"]==18
    assert authority["original_visual_cube_side_m"]==.115
    assert authority["feasibility_cube_side_m"]==.06
    assert authority["native_pybullet_free_dynamic_rigid_body"] is True
    assert authority["fixed_attachment_constraint_added"] is False
    assert layout["same_as_existing_sortcell_viewer_layout"] is False
    assert layout["visual_cad_v11_registered_to_urdf_v10"] is False
    assert layout["physical_mount_calibrated"] is False
    assert layout["all_stage_geometry_tested"] is False
    assert layout["source_fk_validated_original_source_limits"] is True
    assert layout["source_fk_high_transfer_candidates_tested"]>=1
    assert layout["source_fk_interpolated_transfer_min_tcp_z_m"] > (
        layout["pick_source_robot_tcp_m"][2]+.02)
    assert layout["tcp_station_separation_m"]>.5
    stages=motion["stages"]
    assert tuple(row["phase"] for row in stages)==EXPECTED_PHASES
    observations=motion["contact_observations"]
    assert len(observations)>=160
    assert all(isinstance(o["frame"],int) and o["frame"]>=1 for o in observations)
    grouped={name:[s for s in observations if s["phase"]==name]
             for name in EXPECTED_PHASES}
    for row in stages:
        entries=grouped[row["phase"]]
        assert len(entries)==row["series_sample_count"]
        assert entries[-1]==row["last"]
        assert row["bilateral_contact_samples"]==sum(
            x["bilateral_finger_contact"] for x in entries)
        assert entries[-1]["frame"]==row["steps"]
        assert all(a["frame"]<b["frame"] for a,b in zip(entries,entries[1:]))
    # Physical continuity constraint: no unrecorded object jumps. The source
    # simulator sampled at most 10 frames apart (240Hz) so 50mm in 42ms is
    # already a very generous maximum incremental displacement here.
    max_jump=max(math.dist(a["object_xyz_m"],b["object_xyz_m"])
                 for a,b in zip(observations,observations[1:]))
    assert max_jump<.05
    assert motion["no_object_pose_teleports_after_initialization"] is True
    assert motion["no_object_attach_constraints"] is True
    assert motion["initial_robot_cube_overlap_contacts"]==0
    assert motion["initial_cube_pick_floor_overlap_contacts"]==0
    assert motion["supported_grasp_cube_world_xy_offset_m"]==[.02,0]
    assert motion["supported_grasp_cube_orientation"]=="source_tool_aligned"

    grasp=grouped["grasp_close_source_fingers"]
    lift=grouped["lift_under_gravity"]
    raise_=grouped["raise_to_source_fk_clearance"]
    transfer=grouped["source_fk_clearance_transfer"]
    lower=grouped["lower_to_proposed_sort_station"]
    release=grouped["release_open_source_fingers"]
    reset=grouped["reset_robot_without_object_attachment"]
    assert sum(x["bilateral_finger_contact"] for x in grasp)>=20
    assert all(x["bilateral_finger_contact"] for x in lift)
    assert all(x["bilateral_finger_contact"] for x in raise_)
    assert all(x["bilateral_finger_contact"] for x in transfer)
    assert all(x["bilateral_finger_contact"] for x in lower)
    assert all(x["pickup_floor_contacts"]==0 for x in transfer)
    assert all(x["pickup_floor_contacts"]==0 for x in lower)
    assert all(x["pickup_floor_contacts"]==0 for x in raise_)
    assert transfer[-1]["relative_tcp_object_m"]<.035
    assert all(not x["bilateral_finger_contact"] for x in release)
    assert all(not x["bilateral_finger_contact"] for x in reset)
    assert all(x["deposit_floor_contacts"]>0 for x in release)
    assert all(x["deposit_floor_contacts"]>0 for x in reset)

    assert motion["grasp_and_lift_stable"] is True
    assert motion["lift_clear_of_pickup_floor"] is True
    assert motion["clearance_maneuver_remained_off_pickup_floor"] is True
    assert motion["transfer_finger_retention_test"] is True
    assert motion["object_on_deposit_floor_after_release_and_reset"] is True
    assert motion["numerical_full_cycle_test_passed"] is True
    assert motion["object_travel_m"]>.50
    assert motion["physical_sorter_authorized"] is False
    assert motion["real_robot_manipulation_verified"] is False

    final_xyz=reset[-1]["object_xyz_m"]
    station=layout["proposed_fixture_stations"][1]
    center=station["center_robot_xyz_m"]
    assert math.fabs(final_xyz[0]-center[0])<.20
    assert math.fabs(final_xyz[1]-center[1])<.22
    assert math.fabs(final_xyz[2]-(station["surface_height_robot_z_m"]+.03))<.012
    summary={
        "verified_schema":"hardware_splicer.sortcell_strict_numerical_acceptance.v1",
        "source_urdf_sha256":data["original_urdf_sha256"],
        "source_meshes":data["source_collision_meshes"],
        "numerical_full_cycle_passed":True,
        "transfer_observation_count":len(transfer),
        "transfer_bilateral_contact_count":sum(s["bilateral_finger_contact"] for s in transfer),
        "lowering_observation_count":len(lower),
        "lowering_bilateral_contact_count":sum(s["bilateral_finger_contact"] for s in lower),
        "release_observations_without_finger_contact":len(release),
        "reset_observations_supported_by_destination":len(reset),
        "maximum_adjacent_sample_object_displacement_m":round(max_jump,7),
        "destination_cube_center_xyz_m":final_xyz,
        "destination_stage_center_robot_xyz_m":center,
        "source_urdf_version":"v1.0",
        "viewer_cad_version":"v1.1 independently published",
        "source_self_collision_pair_clearance_certified":False,
        "complete_fixture_collision_clearance_certified":False,
        "physically_calibrated_or_actuator_safe":False,
        "hardware_execution_authorized":False,
    }
    return summary


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--cycle",required=True,type=Path)
    parser.add_argument("--urdf",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args()
    result=verify(args.cycle,args.urdf)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))
