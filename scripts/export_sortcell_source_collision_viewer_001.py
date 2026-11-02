#!/usr/bin/env python3
"""Package original OpenArm v1.0 collision STL and real joint-state playback.

Source COLLISION meshes, not source VISUAL DAE or independent v1.1 GLB.
Source link transforms are recalculated from every actual motor-state sample
with the identical manufacturer URDF and untouched source collision meshes.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from scripts.audit_sortcell_openarm_collision_timing_001 import source_meshes
from scripts.solve_sortcell_openarm_pybullet_001 import require, sha

PREFIX="package://openarm_description/"
SCHEMA="hardware_splicer.sortcell_manufacturer_collision_viewer.v1"

def numbers(raw,default):
    return [float(x) for x in (raw if raw is not None else default).split()]

def run(urdf,cycle,wrist,meshes,vendor,viewer_html,output):
    import pybullet as p
    source=urdf.read_bytes()
    c=json.loads(cycle.read_text())
    w=json.loads(wrist.read_text())
    require(c["original_urdf_sha256"]==w["source_urdf_sha256"]==sha(source),
            "source URDF hash mismatch")
    require(c["cycle"]["numerical_full_cycle_test_passed"] is True,
            "original source numerical cycle was not verified")
    require(c["cycle"]["pybullet_source_mimic_constraint_installed"] is True,
            "source mimic coupling must be active")
    require(c["cycle"]["physical_sorter_authorized"] is False,
            "hardware permission cannot be granted")
    require(not output.exists() or not any(output.iterdir()),"output exists")
    output.mkdir(parents=True,exist_ok=True)
    original=ET.fromstring(source)
    upstream={d["upstream_path"]:d for d in w["manufacturer_collision_STL_manifest"]}
    asset_map={}
    for index,uri in enumerate(sorted(set(m.get("filename") for m in original.findall(".//collision//mesh")))):
        require(uri.startswith(PREFIX),"non-original collision mesh URI")
        rel=uri[len(PREFIX):]
        require(".." not in Path(rel).parts and rel in upstream,"unsafe source mesh")
        blob=(meshes/rel).read_bytes()
        require(sha(blob)==upstream[rel]["sha256"],"original source STL hash mismatch")
        dest=output/"meshes"/("source_%02d.stl"%index)
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(blob)
        asset_map[uri]={"relative":"./"+dest.relative_to(output).as_posix(),
                        "sha256":sha(blob),"original_path":rel}
    require(len(asset_map)==11,"original source has unexpected collision mesh count")
    vendor_hash={}
    for filename in ("three.module.js","STLLoader.js","OrbitControls.js"):
        blob=(vendor/filename).read_bytes()
        require(len(blob)>1000,"missing offline Three.js module "+filename)
        dest=output/"vendor"/filename
        dest.parent.mkdir(exist_ok=True)
        dest.write_bytes(blob)
        vendor_hash[filename]=sha(blob)
    source_licenses={}
    for filename,expected in (("LICENSE-OpenArm.txt","Apache License"),
                              ("LICENSE-ThreeJS.txt","MIT License")):
        license_blob=(vendor/filename).read_bytes()
        require(expected.encode() in license_blob and len(license_blob)>500,
                "source license attribution missing: "+filename)
        (output/filename).write_bytes(license_blob)
        source_licenses[filename]=sha(license_blob)
    (output/"index.html").write_bytes(viewer_html.read_bytes())
    source_links=[]
    for link in original.findall("link"):
        shape_list=[]
        for item in link.findall("collision"):
            origin=item.find("origin")
            pos=numbers(origin.get("xyz") if origin is not None else None,"0 0 0")
            angles=numbers(origin.get("rpy") if origin is not None else None,"0 0 0")
            geo=item.find("geometry")
            require(geo is not None,"missing original source collision geometry")
            base={"offset_xyz_m":pos,"offset_quaternion_xyzw":list(p.getQuaternionFromEuler(angles))}
            mesh=geo.find("mesh")
            box=geo.find("box")
            sphere=geo.find("sphere")
            cylinder=geo.find("cylinder")
            if mesh is not None:
                uri=mesh.get("filename")
                require(uri in asset_map,"missing pinned manufacturer collision asset")
                shape={"kind":"original_stl","asset":asset_map[uri]["relative"],
                       "sha256":asset_map[uri]["sha256"],
                       "scale":numbers(mesh.get("scale"),"1 1 1")}
            elif box is not None:
                shape={"kind":"original_box","size":numbers(box.get("size"),"0 0 0")}
            elif sphere is not None:
                shape={"kind":"original_sphere","radius":float(sphere.get("radius"))}
            elif cylinder is not None:
                shape={"kind":"original_cylinder","radius":float(cylinder.get("radius")),
                       "length":float(cylinder.get("length"))}
            else:raise ValueError("unsupported upstream URDF collision geometry")
            shape_list.append({**base,**shape})
        if shape_list:
            source_links.append({"link":link.get("name"),"shapes":shape_list})
    require(len(source_links)>=18,"missing original source geometry links")
    wrist_visual_collision_pairs=[]
    for arm in ("left","right"):
        for linkno in (5,6,7):
            name=f"openarm_{arm}_link{linkno}"
            link=original.find(f"./link[@name='{name}']")
            require(link is not None,"missing source wrist link "+name)
            visual=link.find("visual")
            collision=link.find("collision")
            require(visual is not None and collision is not None,"missing source wrist geometry")
            vm=visual.find(".//mesh")
            cm=collision.find(".//mesh")
            require(vm is not None and cm is not None,"missing original visual/collision wrist meshes")
            vo=visual.find("origin")
            co=collision.find("origin")
            visual_xyz=numbers(vo.get("xyz") if vo is not None else None,"0 0 0")
            collision_xyz=numbers(co.get("xyz") if co is not None else None,"0 0 0")
            visual_rpy=numbers(vo.get("rpy") if vo is not None else None,"0 0 0")
            collision_rpy=numbers(co.get("rpy") if co is not None else None,"0 0 0")
            visual_scale=numbers(vm.get("scale"),"1 1 1")
            collision_scale=numbers(cm.get("scale"),"1 1 1")
            match=(visual_xyz==collision_xyz and visual_rpy==collision_rpy
                   and visual_scale==collision_scale)
            wrist_visual_collision_pairs.append({
                "source_link":name,"manufacturer_source_visual_DAE":vm.get("filename"),
                "manufacturer_source_collision_STL":cm.get("filename"),
                "visual_origin_xyz_m":visual_xyz,"collision_origin_xyz_m":collision_xyz,
                "visual_origin_rpy_rad":visual_rpy,"collision_origin_rpy_rad":collision_rpy,
                "visual_mesh_scale":visual_scale,"collision_mesh_scale":collision_scale,
                "source_URDF_visual_collision_transform_metadata_identical":match,
                "actual_visual_vs_collision_surface_geometry_compared":False})
    require(len(wrist_visual_collision_pairs)==6,"incomplete manufacturer wrist links")
    require(all(x["source_URDF_visual_collision_transform_metadata_identical"]
                for x in wrist_visual_collision_pairs),
            "manufacturer wrist DAE/STL URDF transforms unexpectedly diverged")
    local_root=ET.fromstring(source)
    for link in local_root.findall("link"):
        for visual in link.findall("visual"):link.remove(visual)
    source_meshes(local_root,meshes.resolve())
    # Two distinct faithful URDF representations: original upstream package
    # URI file, plus a copy with *only collision mesh URIs* made relocatable
    # inside the delivered bundle. Neither changes source link origins/joints.
    (output/"manufacturer_original_source.urdf").write_bytes(source)
    portable=ET.fromstring(source)
    for link in portable.findall("link"):
        for visual in link.findall("visual"):link.remove(visual)
    for mesh in portable.findall(".//collision//mesh"):
        uri=mesh.get("filename")
        require(uri in asset_map,"portable source requires known hash-pinned mesh")
        mesh.set("filename",asset_map[uri]["relative"].removeprefix("./"))
    (output/"manufacturer_collision_portable.urdf").write_bytes(
        ET.tostring(portable,encoding="utf8",xml_declaration=True))
    # The physics FK replay still uses original SHA-verified meshes at their
    # runner-local original-source paths, never a newly converted mesh.
    local_urdf=output.parent/"source_collision_runner_paths.urdf"
    local_urdf.write_bytes(ET.tostring(local_root,encoding="utf8",xml_declaration=True))
    client=p.connect(p.DIRECT)
    try:
        flags=p.URDF_MAINTAIN_LINK_ORDER|p.URDF_USE_SELF_COLLISION|p.URDF_USE_SELF_COLLISION_EXCLUDE_PARENT
        robot=p.loadURDF(str(local_urdf),useFixedBase=True,flags=flags,physicsClientId=client)
        ji={}
        li={}
        for j in range(p.getNumJoints(robot,physicsClientId=client)):
            meta=p.getJointInfo(robot,j,physicsClientId=client)
            ji[meta[1].decode()]=j
            li[meta[12].decode()]=j
        source_base=local_root.find("./joint[@name='openarm_body_world_joint']/child").get("link")
        require(all(x["link"]==source_base or x["link"] in li for x in source_links),
                "original collision link is not in physics robot")
        frame_rows=c["cycle"]["contact_observations"]
        require(len(frame_rows)>=270,"not enough original source motor-state samples")
        frames=[]
        for item in frame_rows:
            q=item["source_robot_joint_positions"]
            require(len(q)==18,"original joint-state trace incomplete")
            for n,v in q.items():
                p.resetJointState(robot,ji[n],v,physicsClientId=client)
            p.performCollisionDetection(physicsClientId=client)
            links={}
            for entry in source_links:
                name=entry["link"]
                if name==source_base:
                    pos,quat=p.getBasePositionAndOrientation(robot,physicsClientId=client)
                else:
                    state=p.getLinkState(robot,li[name],computeForwardKinematics=True,
                                         physicsClientId=client)
                    pos,quat=state[4],state[5]
                links[name]={"p":[round(x,6) for x in pos],"q":[round(x,8) for x in quat]}
            orientation=item.get("object_quaternion_xyzw")
            require(isinstance(orientation,list) and len(orientation)==4,
                    "object orientation missing: cannot honestly animate cube")
            frames.append({"phase":item["phase"],"step":item["frame"],
                "links":links,"cube_p":item["object_xyz_m"],"cube_q":orientation,
                "bilateral":item["bilateral_finger_contact"],
                "source_wrist":item["source_robot_self_penetrations"],
                "fixture_hits":item["source_robot_fixture_penetrations"],
                "pickup_support":item["pickup_floor_contacts"],
                "deposit_support":item["deposit_floor_contacts"]})
        supports=[]
        for item in c["candidate_layout"]["proposed_fixture_stations"]:
            sz=item["simulated_proposed_support_size_m"]
            supports.append({"label":item["name"],"p":item["center_robot_xyz_m"],
                             "size":[sz[0],sz[2],sz[1]]})
        manifest={"schema_version":SCHEMA,"source_urdf_sha256":sha(source),
                  "source_robot":"Enactic OpenArm v1.0",
                  "source_collision_mesh_asset_hashes":asset_map,
                  "source_collision_links":source_links,
                  "source_link_count":len(source_links),
                  "original_source_wrist_baseline_penetration_m":w["initial_source_link5_link7_overlap_m"],
                  "source_wrist_visual_vs_collision_metadata":wrist_visual_collision_pairs,
                  "all_source_wrist_DAE_STL_URDF_origins_and_scales_identical":True,
                  "source_visual_DAE_vs_collision_STL_surface_clearance_comparison_done":False,
                  "source_wrist_grid_samples_per_arm":125,
                  "manufacturer_source_visual_DAE_not_included":True,
                  "independent_542_part_v11_GLb_unregistered":True,
                  "source_collision_meshes_not_modified":True,
                  "original_manufacturer_source_urdf_packaged":True,
                  "portable_collision_URDF_relative_mesh_references_packaged":True,
                  "portable_URDF_only_collision_mesh_references_changed":True,
                  "original_joint_and_link_frames_not_modified":True,
                  "viewer_offline_vendor_module_hashes":vendor_hash,
                  "pinned_open_source_license_notices_SHA256":source_licenses,
                  "physical_robot_approved":False}
        poses={"schema_version":"hardware_splicer.sortcell_source_collision_pose_replay.v1",
               "source_urdf_sha256":sha(source),"z_up":True,
               "original_source_motor_samples":len(frames),
               "frames":frames,"supports":supports,"cube_side":.06,
               "no_v11_registration":True,"hardware_authorized":False}
        (output/"source_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
        (output/"source_motion.json").write_text(json.dumps(poses,separators=(",",":"))+"\n")
        (output/"README.md").write_text(
            "# SORTCELL manufacturer-source collision viewer\n\n"
            "Run a static local HTTP server in this exported viewer folder "
            "(for example, python -m http.server 8000) and open "
            "http://localhost:8000/ . Files include offline Three.js modules "
            "and SHA-verified original OpenArm v1.0 collision STLs. "
            "Playback uses actual motor joint-position samples, source frame FK "
            "and source PyBullet object orientation. "
            "THIS IS ORIGINAL COLLISION GEOMETRY, not manufacturer VISUAL DAE "
            "or independent v1.1 542-part CAD. Source wrist penetration persists. "
            "Proposed fixture support boxes are numerical assumptions only. "
            "Nothing here is calibrated to actual hardware or authorized to drive it.\n")
        return {"source_urdf_sha256":sha(source),"frame_count":len(frames),
                "source_collision_links":len(source_links),
                "source_STL_meshes":len(asset_map),"physical_motion_authorized":False}
    finally:p.disconnect(physicsClientId=client)

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    for key in ("urdf","cycle","wrist","meshes","vendor","viewer-html","output"):
        ap.add_argument("--"+key,required=True,type=Path)
    a=ap.parse_args()
    print(json.dumps(run(a.urdf,a.cycle,a.wrist,a.meshes,a.vendor,a.viewer_html,a.output),indent=2))
