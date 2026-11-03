#!/usr/bin/env python3
"""Compare OFFICIAL OpenArm v1.0 wrist visual DAE and collision STL surfaces.

Source geometry: enactic/openarm_description at the exact pinned source commit.
Each visual & collision surface is loaded using a common trimesh importer,
multiplied by its original URDF XYZ scale (including negative Y on left),
and checked per original source link. Comparisons are *sampled nearest
surface-distance estimates*, not exact Hausdorff distance or a certificate
that two assembled solids do/do-not collide. PyBullet may use convex hulls
for mesh contacts; source mesh penetrations are never suppressed here.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request,urlopen
import xml.etree.ElementTree as ET

SOURCE_COMMIT="2e27c793e10aa2045e7eb597b9b9b9dc08fb0a08"
SOURCE_RAW="https://raw.githubusercontent.com/enactic/openarm_description/"+SOURCE_COMMIT+"/"
PACKAGE="package://openarm_description/"
SCHEMA="hardware_splicer.sortcell_original_wrist_dae_stl_surface_audit.v1"
EXPECTED_URDF_SHA="763d8e0280479cd4d9868e977c9c01416b9f83c8899c95b918446c0cfaf32f11"

def insist(condition,message):
    if not condition:raise ValueError("original source geometry audit: "+message)

def sha(data):return hashlib.sha256(data).hexdigest()

def fetch_original(uri,asset_root):
    insist(uri.startswith(PACKAGE),"non-original source asset URI")
    rel=uri[len(PACKAGE):]
    insist(".." not in Path(rel).parts and
           (rel.endswith(".dae") or rel.endswith(".stl")),"invalid original geometry path")
    loc=asset_root/rel
    if loc.is_file():
        blob=loc.read_bytes()
    else:
        url=SOURCE_RAW+quote(rel,safe="/")
        with urlopen(Request(url,headers={"User-Agent":"hardware-splicer-original-wrist-surface-study"}),
                     timeout=60) as conn:
            blob=conn.read(35_000_001)
        insist(len(blob)<35_000_001,"oversized upstream asset "+rel)
        insist(not blob.startswith(b"version https://git-lfs.github.com/spec/v1"),
               "upstream LFS pointer instead of original geometry")
        loc.parent.mkdir(parents=True,exist_ok=True)
        loc.write_bytes(blob)
    insist(84<len(blob)<35_000_001,"missing/oversized official geometry "+rel)
    return loc,{"uri":uri,"relative_path":rel,"url":SOURCE_RAW+quote(rel,safe="/"),
                "sha256":sha(blob),"byte_count":len(blob)}

def vectors(raw,default="0 0 0"):
    return [float(x) for x in (default if raw is None else raw).split()]

def get_geom(link,kind):
    item=link.find(kind)
    insist(item is not None,f"original {link.get('name')} missing {kind}")
    mesh=item.find("./geometry/mesh")
    insist(mesh is not None,f"original {link.get('name')} {kind} not mesh")
    origin=item.find("origin")
    return {
        "URI":mesh.get("filename"),
        "scale":vectors(mesh.get("scale"),"1 1 1"),
        "xyz":vectors(origin.get("xyz") if origin is not None else None),
        "rpy":vectors(origin.get("rpy") if origin is not None else None),
    }

def get_original_trimesh(path):
    import trimesh
    loaded=trimesh.load(str(path),force="scene",process=False)
    if isinstance(loaded,trimesh.Trimesh):
        mesh=loaded
        meshes=1
    else:
        meshes=len(loaded.geometry)
        mesh=loaded.to_mesh()
    insist(isinstance(mesh,trimesh.Trimesh),"source geometry could not be parsed "+str(path))
    insist(len(mesh.faces)>15 and len(mesh.vertices)>15,"empty source mesh "+str(path))
    insist(mesh.vertices.shape[1]==3 and mesh.faces.shape[1]==3,
           "source mesh not triangulated "+str(path))
    return mesh,int(meshes)

def source_geometry(mesh,scale):
    import trimesh
    cp=mesh.copy()
    cp.apply_transform(__import__("numpy").diag([*scale,1]))
    return cp

def surface_cloud(mesh,n,seed):
    import trimesh
    import numpy as np
    sampled=trimesh.sample.sample_surface(mesh,n,seed=seed)[0]
    # Add all vertices when manageable; sampling only surface points would
    # systematically miss extreme extents and thin features.
    vertices=np.asarray(mesh.vertices,dtype=np.float64)
    if len(vertices)>n:
        rng=np.random.default_rng(seed)
        vertices=vertices[rng.choice(len(vertices),n,replace=False)]
    return np.vstack((sampled,vertices))

def surface_distances(visual,collision,seed=91):
    import numpy as np
    from scipy.spatial import cKDTree
    vis=surface_cloud(visual,5500,seed)
    col=surface_cloud(collision,5500,seed+1)
    v_to_c=cKDTree(col).query(vis,k=1,workers=1)[0]
    c_to_v=cKDTree(vis).query(col,k=1,workers=1)[0]
    def q(a):
        return {key:round(float(np.percentile(a,x)),7)
                for key,x in (("p50",50),("p90",90),("p95",95),("p99",99),("p100",100))}
    return {
        "method":"bidirectional sampled approximate nearest-surface distances via scipy.cKDTree",
        "visual_cloud_samples":len(vis),
        "collision_cloud_samples":len(col),
        "visual_to_collision_distance_m":q(v_to_c),
        "collision_to_visual_distance_m":q(c_to_v),
        "symmetric_sampled_max_distance_m":round(float(max(v_to_c.max(),c_to_v.max())),7),
        "symmetric_sampled_p95_distance_m":round(float(max(np.percentile(v_to_c,95),
                                                         np.percentile(c_to_v,95))),7),
        "exact_hausdorff_or_signed_interpenetration_measured":False,
    }

def metrics(mesh):
    import numpy as np
    b=np.asarray(mesh.bounds,dtype=np.float64)
    return {
        "triangle_faces":int(len(mesh.faces)),
        "vertices":int(len(mesh.vertices)),
        "bounds_m":[[round(float(x),6) for x in row] for row in b],
        "extent_xyz_m":[round(float(x),6) for x in mesh.extents],
        "surface_area_m2":round(float(mesh.area),7),
        "watertight":bool(mesh.is_watertight),
        "winding_consistent":bool(mesh.is_winding_consistent),
        "body_count":int(mesh.body_count),
        "convex_hull_to_mesh_volume_ratio":(
           round(float(mesh.convex_hull.volume/max(mesh.volume,1e-12)),4)
           if mesh.is_watertight and mesh.volume>1e-12 else None),
    }

def run(urdf_path,output,upstream_collision_manifest=None):
    import numpy as np
    source=urdf_path.read_bytes()
    insist(sha(source)==EXPECTED_URDF_SHA,"pinned manufacturer URDF hash changed")
    root=ET.fromstring(source)
    insist(root.get("name")=="openarm","not manufacturer OpenArm")
    existing={}
    if upstream_collision_manifest:
        w=json.loads(upstream_collision_manifest.read_text())
        insist(w["source_urdf_sha256"]==sha(source),"source wrist diagnosis hash differs")
        existing={x["upstream_path"]:x["sha256"] for x in w["manufacturer_collision_STL_manifest"]}
    output.mkdir(parents=True,exist_ok=True)
    assert not list(output.iterdir()),"refuse to overwrite existing analysis"
    assets=output/"manufacturer-source"
    files={}
    per_link=[]
    for side in ("left","right"):
        for number in (5,6,7):
            name=f"openarm_{side}_link{number}"
            link=root.find(f"./link[@name='{name}']")
            insist(link is not None,"missing source wrist link "+name)
            v=get_geom(link,"visual")
            c=get_geom(link,"collision")
            insist(v["URI"].endswith(".dae") and c["URI"].endswith(".stl"),
                   "source wrist DAE/STL formats unexpected")
            insist(v["scale"]==c["scale"] and v["xyz"]==c["xyz"] and
                   v["rpy"]==c["rpy"],"manufacturer wrist DAE/STL origin or scale mismatch")
            for item in (v,c):
                uri=item["URI"]
                if uri not in files:
                    path,prov=fetch_original(uri,assets)
                    if uri.endswith(".stl") and existing:
                        insist(prov["sha256"]==existing[prov["relative_path"]],
                               "manufacturer wrist STL hash changed")
                    files[uri]={**prov,"path":str(path)}
            vmesh,v_components=get_original_trimesh(Path(files[v["URI"]]["path"]))
            cmesh,c_components=get_original_trimesh(Path(files[c["URI"]]["path"]))
            vmesh=source_geometry(vmesh,v["scale"])
            cmesh=source_geometry(cmesh,c["scale"])
            d=surface_distances(vmesh,cmesh)
            per_link.append({
                "source_link_name":name,
                "source_visual_geometry_uri":v["URI"],
                "source_collision_geometry_uri":c["URI"],
                "original_source_visual_and_collision_metadata_equal":True,
                "source_scale_xyz":v["scale"],
                "source_origin_xyz_m":v["xyz"],
                "source_origin_rpy_rad":v["rpy"],
                "visual_DAE_scene_components":v_components,
                "collision_STL_scene_components":c_components,
                "original_source_visual_mesh":metrics(vmesh),
                "original_source_collision_mesh":metrics(cmesh),
                "sampled_surface_comparison":d,
                "CAD_surface_equivalence_proven":False,
                "physical_wrist_clearance_proven":False,
            })
    insist(len(per_link)==6 and len(files)==6,"source original wrist asset coverage incomplete")
    # This method identifies shape disagreement, NOT definitive penetration:
    # visual meshes may have holes, simplify collision STLs may use convex hulls.
    return {
      "schema_version":SCHEMA,
      "manufacturer_repo":"enactic/openarm_description",
      "manufacturer_pinned_commit":SOURCE_COMMIT,
      "manufacturer_original_urdf_sha256":sha(source),
      "source_wrist_assets":[{k:v for k,v in x.items() if k!="path"} for x in files.values()],
      "six_source_wrist_link_comparisons":per_link,
      "summary":{
          "original_source_wrist_links_compared":len(per_link),
          "unique_upstream_DAE":sum(x["relative_path"].endswith(".dae") for x in files.values()),
          "unique_upstream_collision_STL":sum(x["relative_path"].endswith(".stl") for x in files.values()),
          "maximum_symmetric_sampled_surface_distance_m":max(
              x["sampled_surface_comparison"]["symmetric_sampled_max_distance_m"] for x in per_link),
          "maximum_symmetric_p95_surface_distance_m":max(
              x["sampled_surface_comparison"]["symmetric_sampled_p95_distance_m"] for x in per_link),
          "all_original_URDF_collision_meshes_unchanged":True,
          "exact_mesh_mesh_intersection_of_assembled_links_evaluated":False,
          "pybullet_collision_convexity_impact_qualified":False,
          "manufacturer_collision_STL_vs_visual_DAE_approximated_not_certified":True,
          "independent_v11_542_part_CAD_frame_registered":False,
          "robot_hardware_motion_authorized":False,
      },
    }

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--urdf",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--collision-manifest",type=Path)
    args=parser.parse_args()
    evidence=run(args.urdf,args.output,args.collision_manifest)
    path=args.output/"WRIST_VISUAL_DAE_VS_COLLISION_STL.json"
    path.write_text(json.dumps(evidence,indent=2)+"\n")
    print(json.dumps({"schema":evidence["schema_version"],
                       "links":evidence["summary"]["original_source_wrist_links_compared"],
                       "maximum_sampled_distance_m":evidence["summary"]["maximum_symmetric_sampled_surface_distance_m"],
                       "maximum_sampled_p95_distance_m":evidence["summary"]["maximum_symmetric_p95_surface_distance_m"],
                       "hardware_motion_authorized":False},indent=2))
