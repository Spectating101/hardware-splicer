#!/usr/bin/env python3
"""Validate offline original v1.0 collision meshes + sampled source-FK replay.

Independent of exporter implementation. Collision mesh renderer is NOT visual
DAE, independent v1.1 542-part CAD or physical safety certification.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

SCHEMA="hardware_splicer.sortcell_manufacturer_collision_viewer.v1"

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(urdf,cycle,package):
    src=urdf.read_bytes();h=hashlib.sha256(src).hexdigest()
    xml=ET.fromstring(src)
    expected={x.get("filename") for x in xml.findall(".//collision//mesh")}
    manifest=json.loads((package/"source_manifest.json").read_text())
    trace=json.loads((package/"source_motion.json").read_text())
    if manifest["schema_version"]!=SCHEMA or manifest["source_urdf_sha256"]!=h or trace["source_urdf_sha256"]!=h:
        raise ValueError("upstream source provenance mismatch")
    if len(expected)!=11 or set(manifest["source_collision_mesh_asset_hashes"])!=expected:
        raise ValueError("incomplete source original STL manifest")
    for _,item in manifest["source_collision_mesh_asset_hashes"].items():
        path=(package/item["relative"]).resolve()
        if not path.is_relative_to(package.resolve()):raise ValueError("path traversal")
        if digest(path)!=item["sha256"]:raise ValueError("manufacturer original source STL changed")
    if not trace["z_up"] or trace["hardware_authorized"] or not trace["no_v11_registration"]:
        raise ValueError("unsupported source coordinate/safety claim")
    source_case=json.loads(cycle.read_text())
    rows=source_case["cycle"]["contact_observations"]
    if trace["original_source_motor_samples"]!=len(rows) or len(trace["frames"])!=len(rows):
        raise ValueError("not every source motor state sampled")
    if len(rows)<270 or manifest["source_link_count"]<18:raise ValueError("incomplete engineering view")
    link_names={x["link"] for x in manifest["source_collision_links"]}
    if len(link_names)!=manifest["source_link_count"]:raise ValueError("ambiguous source link identities")
    for row,frame in zip(rows,trace["frames"]):
        if frame["phase"]!=row["phase"] or frame["step"]!=row["frame"]:
            raise ValueError("source original motor observation order changed")
        if set(frame["links"])!=link_names:raise ValueError("source FK link poses missing")
        for pose in frame["links"].values():
            if len(pose["p"])!=3 or len(pose["q"])!=4:
                raise ValueError("source link world pose incomplete")
        if len(frame["cube_q"])!=4 or frame["cube_p"]!=row["object_xyz_m"]:
            raise ValueError("free object source pose inconsistent")
        if frame["bilateral"]!=row["bilateral_finger_contact"]:
            raise ValueError("source gripper contact status changed")
        if frame["source_wrist"]!=row["source_robot_self_penetrations"]:
            raise ValueError("original source wrist overlapping pairs hidden")
        if frame["fixture_hits"]!=row["source_robot_fixture_penetrations"]:
            raise ValueError("original source fixture collisions hidden")
    if manifest["independent_542_part_v11_GLb_unregistered"] is not True:
        raise ValueError("independent visual v1.1 cannot be falsely registered")
    if manifest["source_collision_meshes_not_modified"] is not True:
        raise ValueError("original source geometry must stay unmodified")
    if manifest["physical_robot_approved"] is not False:
        raise ValueError("cannot authorize hardware use")
    pairs=manifest.get("source_wrist_visual_vs_collision_metadata",[])
    if len(pairs)!=6 or not manifest.get("all_source_wrist_DAE_STL_URDF_origins_and_scales_identical"):
        raise ValueError("manufacturer wrist source visual/collision transform check missing")
    for part in pairs:
        n=part["source_link"]
        link=xml.find("./link[@name='"+n+"']")
        if link is None:raise ValueError("original wrist link missing")
        v=link.find("visual");c=link.find("collision")
        vm=v.find(".//mesh");cm=c.find(".//mesh")
        if (part["manufacturer_source_visual_DAE"]!=vm.get("filename") or
            part["manufacturer_source_collision_STL"]!=cm.get("filename")):
            raise ValueError("wrist mesh original reference mismatch")
        if not vm.get("filename").endswith(".dae") or not cm.get("filename").endswith(".stl"):
            raise ValueError("mixed source mesh formats changed")
        if part["actual_visual_vs_collision_surface_geometry_compared"]:
            raise ValueError("false source surface-clearance comparison claim")
        if not part["source_URDF_visual_collision_transform_metadata_identical"]:
            raise ValueError("source URDF wrist visual collision transforms differ")
    if manifest["source_visual_DAE_vs_collision_STL_surface_clearance_comparison_done"]:
        raise ValueError("not yet qualified original manufacturer visual and collision surfaces")
    if manifest["source_wrist_grid_samples_per_arm"]!=125:
        raise ValueError("original wrist evidence changed")
    if len(trace["supports"])!=2:raise ValueError("missing real candidate support planes")
    for name in ("three.module.js","STLLoader.js","OrbitControls.js"):
        if digest(package/"vendor"/name)!=manifest["viewer_offline_vendor_module_hashes"][name]:
            raise ValueError("packaged offline Three.js module hash mismatch")
    html=(package/"index.html").read_text()
    if not all(x in html for x in ("source_manifest.json","source_motion.json",
                                  "STLLoader.js","OrbitControls.js",
                                  "NOT SOURCE VISUAL CAD", "PHYSICALLY CERTIFIED")):
        raise ValueError("viewer source or scope disclaimer missing")
    return {
       "schema_version":"hardware_splicer.sortcell_original_source_collision_viewer_acceptance.v1",
       "manufacturer_source_urdf_sha256":h,
       "original_source_STL_assets_hash_verified":len(expected),
       "original_source_collision_link_count":len(link_names),
       "independent_source_motor_world_pose_frames":len(rows),
       "every_source_joint_and_cube_frame_retained":True,
       "original_wrist_contact_evidence_retained":True,
       "manufacturer_source_wrist_DAE_STL_transform_metadata_matched_for_six_links":True,
       "actual_visual_collision_mesh_surface_comparison_executed":False,
       "all_three_offline_viewer_dependencies_hash_verified":True,
       "original_source_collision_geometry_not_visual_DAE":True,
       "visual_v11_GLb_to_source_v10_registered":False,
       "browser_rendering_executed_in_ci":False,
       "physical_robot_motion_authorized":False,
       "continuous_collision_clearance_certified":False,
    }

if __name__=="__main__":
    a=argparse.ArgumentParser()
    for n in ("urdf","cycle","package","output"):a.add_argument("--"+n,required=True,type=Path)
    v=a.parse_args()
    r=run(v.urdf,v.cycle,v.package)
    v.output.parent.mkdir(parents=True,exist_ok=True)
    v.output.write_text(json.dumps(r,indent=2)+"\n")
    print(json.dumps(r,indent=2))
