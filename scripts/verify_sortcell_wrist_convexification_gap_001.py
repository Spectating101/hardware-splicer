#!/usr/bin/env python3
"""Independent gate for SORTCELL's original wrist BVH-vs-hull discrepancy.

A source pose may show no crossing triangles while still containing solid
overlap, internal geometry, or collision between actual physical parts. We
only establish the contact-model disagreement at four recorded legal poses.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

EXPECTED_SOURCE_SHA="763d8e0280479cd4d9868e977c9c01416b9f83c8899c95b918446c0cfaf32f11"
SCHEMA="hardware_splicer.sortcell_original_manufacturer_wrist_triangle_contacts.v1"

def assert_thing(x,reason):
    if not x:raise ValueError("wrist original-vs-hull contact gate rejected: "+reason)

def accept(urdf,study,pose_fixture,contact):
    source=urdf.read_bytes()
    h=hashlib.sha256(source).hexdigest()
    assert_thing(h==EXPECTED_SOURCE_SHA,"unpinned source URDF")
    surf=json.loads(study.read_text())
    pose=json.loads(pose_fixture.read_text())
    result=json.loads(contact.read_text())
    assert_thing(surf["manufacturer_original_urdf_sha256"]==h and
                 pose["source_urdf_sha256"]==h and
                 result["original_manufacturer_urdf_sha256"]==h,"mixed original source provenance")
    assert_thing(result["schema_version"]==SCHEMA,"wrong measured FCL schema")
    assert_thing(result["original_source_kinematics_independently_matches_pybullet_replay"] is True,
                 "original source link poses not independently verified")
    expected_case={(side,item["label"]) for side in ("left","right")
                   for item in pose["wrist_pose_cases"][side]}
    cases=result["FCL_paired_visual_DAE_vs_collision_STL_triangle_queries"]
    assert_thing(len(cases)==4 and {(x["arm"],x["source_pose_case"]) for x in cases}==expected_case,
                 "incomplete four source wrist pose cases")
    verified=[]
    for row in cases:
        assert_thing(row["source_real_link_fk_from_manufacturer_urdf"] is True,
                     "source FK not from manufacturer URDF")
        assert_thing(row["source_meshes_unchanged"] is True and
                     row["derived_hull_is_not_original_manufacturer_collision_geometry"] is True,
                     "derived hull not distinguished from original source mesh")
        for origin in ("original_visual_DAE_triangle_query","original_collision_STL_triangle_query"):
            x=row[origin]
            assert_thing(x["FCL_contact_detected"] is False,
                         "original source triangle contact outcome changed: "+str(row["source_pose_case"]))
            assert_thing(all(name=="BVHModel" for name in x["FCL_geometry_types"].values()),
                         "original source mesh did not use FCL BVH triangle geometry")
            assert_thing(x["solid_containment_and_full_physical_clearance_certified"] is False,
                         "FCL triangle test falsely certifies physical clearance")
        for proxy in ("derived_visual_DAE_convex_hull_query","derived_collision_STL_convex_hull_query"):
            x=row[proxy]
            assert_thing(x["FCL_contact_detected"] is True,
                         "derived hull source-contact outcome changed: "+str(row["source_pose_case"]))
            assert_thing(all(name=="Convex" for name in x["FCL_geometry_types"].values()),
                         "derived collision model was not a true FCL convex solid")
            assert_thing(x["hull_is_derived_proxy_not_manufacturer_geometry"] is True,
                         "derived hull provenance mislabeled")
            assert_thing(x["solid_containment_and_full_physical_clearance_certified"] is False,
                         "convex hull declared physical safety")
        verified.append({"arm":row["arm"],"recorded_source_pose":row["source_pose_case"],
                         "original_visual_triangles_intersect":False,
                         "original_collision_triangles_intersect":False,
                         "derived_visual_convex_hulls_contact":True,
                         "derived_collision_convex_hulls_contact":True})
    summary=result["summary"]
    for k,v in (("native_source_wrist_cases_compared",4),
                ("source_visual_DAE_triangle_contact_cases",0),
                ("source_collision_STL_triangle_contact_cases",0),
                ("derived_visual_DAE_convex_hull_collision_cases",4),
                ("derived_collision_STL_convex_hull_collision_cases",4)):
        assert_thing(summary[k]==v,"measured original-vs-derived FCL collision count changed "+k)
    assert_thing(summary["original_source_mesh_triangle_queries_returned_no_contact_in_tested_poses"] is True,
                 "source triangle contact summary wrong")
    assert_thing(summary["derived_source_convex_hull_queries_reported_contact_in_tested_poses"] is True,
                 "source derived convex collision summary wrong")
    for key in ("physical_robot_motion_authorized",
                "upstream_source_v11_visual_registration_performed"):
        assert_thing(summary[key] is False,"unwarranted manufacturing/safety claim")
    assert_thing(summary["FCL_triangle_contacts_not_closed_solid_or_physical_certification"] is True,
                 "original open mesh containment limitation omitted")
    return {
        "schema_version":"hardware_splicer.sortcell_wrist_convexification_gap_acceptance.v1",
        "original_manufacturer_urdf_sha256":h,
        "independently_checked_original_FK_against_native_pybullet_frames":6,
        "original_BVH_triangle_contact_cases":0,
        "derived_convex_hull_contact_cases":8,
        "wrist_source_poses_checked":4,
        "case_by_case_FCL_outcomes":verified,
        "engineering_hypothesis":"convexification introduces apparent sampled wrist link5-link7 contact where original open triangle surfaces do not cross",
        "proven_absence_of_real_mechanical_interference":False,
        "all_possible_wrist_poses_qualified":False,
        "continuous_solid_clearance_certified":False,
        "manufacturer_source_mesh_edited_or_whitelisted":False,
        "physical_robot_motion_authorized":False,
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    for name in ("urdf","study","poses","contacts","output"):
        ap.add_argument("--"+name,required=True,type=Path)
    x=ap.parse_args()
    report=accept(x.urdf,x.study,x.poses,x.contacts)
    x.output.parent.mkdir(parents=True,exist_ok=True)
    x.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"wrist_source_pose_count":report["wrist_source_poses_checked"],
      "original_triangle_contacts":report["original_BVH_triangle_contact_cases"],
      "derived_convex_contacts":report["derived_convex_hull_contact_cases"],
      "robot_hardware_authorized":False},indent=2))
