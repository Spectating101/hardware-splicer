#!/usr/bin/env python3
"""Independently validate pinned six-link source DAE/STL wrist-surface evidence.

The presence of bidirectional nearest-neighbor measurements does not establish
a geometrically exact Hausdorff distance or robot self-collision clearance.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

SOURCE_HASH="763d8e0280479cd4d9868e977c9c01416b9f83c8899c95b918446c0cfaf32f11"
SOURCE_COMMIT="2e27c793e10aa2045e7eb597b9b9b9dc08fb0a08"
SCHEMA="hardware_splicer.sortcell_original_wrist_dae_stl_surface_audit.v1"
PREFIX="package://openarm_description/"

def require(x,why):
    if not x:raise ValueError("original wrist surface acceptance rejected: "+why)

def run(urdf:Path,study:Path)->dict:
    raw=urdf.read_bytes()
    h=hashlib.sha256(raw).hexdigest()
    require(h==SOURCE_HASH,"incorrect original manufacturer URDF revision")
    root=ET.fromstring(raw)
    r=json.loads(study.read_text())
    require(r["schema_version"]==SCHEMA,"wrong evidence schema")
    require(r["manufacturer_pinned_commit"]==SOURCE_COMMIT,"wrong manufacturer commit")
    require(r["manufacturer_original_urdf_sha256"]==h,"study uses wrong source")
    links=r["six_source_wrist_link_comparisons"]
    expected={f"openarm_{side}_link{index}" for side in ("left","right")
             for index in (5,6,7)}
    require(len(links)==6 and {x["source_link_name"] for x in links}==expected,
            "incomplete six manufacturer wrist links")
    assets={a["uri"]:a for a in r["source_wrist_assets"]}
    require(len(assets)==6,"expected 3 visual DAEs and 3 collision STLs")
    require(sum(k.endswith(".dae") for k in assets)==3,"missing visual original DAE")
    require(sum(k.endswith(".stl") for k in assets)==3,"missing original collision STL")
    for uri,asset in assets.items():
        require(uri.startswith(PREFIX) and ".." not in Path(uri[len(PREFIX):]).parts,
                "untrusted manufacturer wrist geometry")
        require(len(asset["sha256"])==64 and asset["byte_count"]>84,
                "missing source geometry SHA/size")
        original_path=study.parent/"manufacturer-source"/asset["relative_path"]
        require(original_path.is_file(),"source file not in evidence bundle "+asset["relative_path"])
        require(hashlib.sha256(original_path.read_bytes()).hexdigest()==asset["sha256"],
                "official upstream source geometry changed from reported checksum")
        require(SOURCE_COMMIT in asset["url"],"asset URL unpinned")
    results=[]
    for record in links:
        name=record["source_link_name"]
        upstream=root.find("./link[@name='"+name+"']")
        require(upstream is not None,"source wrist link missing: "+name)
        for kind,field in (("visual","source_visual_geometry_uri"),
                           ("collision","source_collision_geometry_uri")):
            original=upstream.find(kind)
            mesh=original.find("./geometry/mesh") if original is not None else None
            require(mesh is not None and mesh.get("filename")==record[field],
                    "wrong manufacturer mesh for "+name)
            require(mesh.get("filename") in assets,"source part not hash verified")
        require(record["original_source_visual_and_collision_metadata_equal"],
                "unreported origin/scale disagreement")
        require(record["CAD_surface_equivalence_proven"] is False and
                record["physical_wrist_clearance_proven"] is False,
                "false surface or physical clearance claim")
        v=record["original_source_visual_mesh"]
        c=record["original_source_collision_mesh"]
        for shape in (v,c):
            require(shape["triangle_faces"]>15 and shape["vertices"]>15,
                    "mesh was not triangulated")
            require(len(shape["bounds_m"])==2 and len(shape["extent_xyz_m"])==3,
                    "source geometry missing 3D shape bounds")
            require(all(math.isfinite(x) and x>0 for x in shape["extent_xyz_m"]),
                    "invalid real source mesh extent")
        d=record["sampled_surface_comparison"]
        require(d["exact_hausdorff_or_signed_interpenetration_measured"] is False,
                "sampled nearest-surface metric misrepresented as exact")
        require(d["visual_cloud_samples"]>=5000 and d["collision_cloud_samples"]>=5000,
                "insufficient surface sample coverage")
        for direction in ("visual_to_collision_distance_m","collision_to_visual_distance_m"):
            q=d[direction]
            values=[q[key] for key in ("p50","p90","p95","p99","p100")]
            require(all(math.isfinite(x) and x>=0 for x in values),
                    "missing finite surface measurement")
            require(values==sorted(values),"percentile order not monotonic")
        results.append({"link":name,
                        "source_visual_triangles":v["triangle_faces"],
                        "source_collision_triangles":c["triangle_faces"],
                        "sampled_symmetrical_p95_m":d["symmetric_sampled_p95_distance_m"],
                        "sampled_max_m":d["symmetric_sampled_max_distance_m"]})
    summary=r["summary"]
    require(summary["original_source_wrist_links_compared"]==6 and
            summary["unique_upstream_DAE"]==3 and
            summary["unique_upstream_collision_STL"]==3,"count mismatch")
    require(summary["all_original_URDF_collision_meshes_unchanged"] is True,
            "original manufacturer collision geometry altered")
    for key in ("exact_mesh_mesh_intersection_of_assembled_links_evaluated",
                "pybullet_collision_convexity_impact_qualified",
                "independent_v11_542_part_CAD_frame_registered",
                "robot_hardware_motion_authorized"):
        require(summary[key] is False,"unwarranted robot safety/registration claim: "+key)
    return {"schema_version":"hardware_splicer.sortcell_wrist_surface_audit_verification.v1",
            "official_source_urdf_sha256":h,
            "all_six_source_wrist_surface_links_verified":True,
            "visual_DAE_assets_original_SHA256_verified":3,
            "collision_STL_assets_original_SHA256_verified":3,
            "surface_comparisons":results,
            "exact_surface_intersections_established":False,
            "physical_wrist_clearance_certified":False,
            "physical_robot_command_authorized":False}

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--urdf",type=Path,required=True)
    ap.add_argument("--study",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    r=run(args.urdf,args.study)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(r,indent=2)+"\n")
    print(json.dumps({"source_verified":r["all_six_source_wrist_surface_links_verified"],
                      "surfaces":[(d["link"],d["sampled_symmetrical_p95_m"]) for d in r["surface_comparisons"]],
                      "physical_motion_authorized":False},indent=2))
