"""Actual native CADCLAW assembly STEP -> named GLB meshes for Teardown.

Matches each native solid to the independently authored part by volume and
bounds. Rejects ambiguous assignments, foreign parts and missing STEP evidence.
No real-world fit, physical pressure, or mechanism motion authority.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
from .multicad_toolchain import validate_manifest, check_native_outputs, digest, require, canonical


def assemble_mesh(multicad: Path, cadclaw: Path, out: Path) -> dict:
    multicad=Path(multicad)
    cadclaw=Path(cadclaw)
    out=Path(out)
    manifest=validate_manifest(multicad)
    check_native_outputs(multicad)
    import cadquery as cq
    import trimesh
    import numpy as np
    input_receipt=json.loads((cadclaw/"CADCLAW_INPUT_RECEIPT.json").read_text())
    require(input_receipt.get("source_spec_sha256")==manifest["source_spec_sha256"] and
            input_receipt.get("product_id")==manifest["product_id"] and
            input_receipt.get("physical_release_authorized") is False,
            "CADCLAW assembly not source-bound")
    assembly=cadclaw/"clearbench_s1_dry_reference.step"
    require(assembly.is_file() and assembly.stat().st_size>1000,"missing actual CADCLAW native assembly")
    shape=cq.importers.importStep(str(assembly))
    solids=shape.solids().vals()
    parts=manifest["parts"]
    require(len(solids)==len(parts),"native assembly does not have exactly the expected parts")
    references=[]
    for p in parts:
        f=multicad/"partcad"/"parts"/f'{p["id"]}.step'
        original=cq.importers.importStep(str(f)).solids().vals()
        require(len(original)==1,"non-single source part")
        references.append((p,original[0].Volume(),original[0].BoundingBox()))
    unmatched=list(range(len(references)))
    matched=[]
    for s in solids:
        vol=s.Volume()
        box=s.BoundingBox()
        dim=sorted((box.xlen,box.ylen,box.zlen))
        candidates=[]
        for i in unmatched:
            p,v,b=references[i]
            expected=sorted((b.xlen,b.ylen,b.zlen))
            if math.isclose(vol,v,rel_tol=.002,abs_tol=.03) and all(
                math.isclose(x,y,abs_tol=.25) for x,y in zip(dim,expected)
            ):
                candidates.append(i)
        require(len(candidates)==1,"native STEP solid identity ambiguous or missing")
        i=candidates[0]
        unmatched.remove(i)
        matched.append((references[i][0],s))
    require(not unmatched,"native assembly omitted parts")
    scene=trimesh.Scene()
    report=[]
    bbox=shape.val().BoundingBox()
    center=np.array([(bbox.xmin+bbox.xmax)/2,(bbox.ymin+bbox.ymax)/2,(bbox.zmin+bbox.zmax)/2])
    span=max(bbox.xlen,bbox.ylen,bbox.zlen)
    require(span>0,"degenerate assembly STEP")
    scale=8.0/span
    # X,Z source -> X,Y viewer, Y source -> -Z viewer; right-handed transform.
    for part,solid in matched:
        verts,faces=solid.tessellate(.5,.25)
        require(len(verts)>20 and len(faces)>10,"insufficient native tessellation")
        v=np.asarray([(p.x,p.z,-p.y) for p in verts],dtype=np.float64)
        v=(v-np.array([center[0],center[2],-center[1]]))*scale
        f=np.asarray(faces,dtype=np.int64)
        mesh=trimesh.Trimesh(vertices=v,faces=f,process=False)
        require(mesh.is_volume and mesh.is_watertight,"native part tessellation not watertight solid")
        scene.add_geometry(mesh,node_name=part["id"],geom_name=part["id"])
        report.append({"id":part["id"],"triangles":int(len(mesh.faces)),
                       "mesh_volume_mm3":round(float(abs(mesh.volume)/scale**3),2),
                       "cad_volume_mm3":round(solid.Volume(),2)})
    out.mkdir(parents=True,exist_ok=True)
    raw=scene.export(file_type="glb")
    require(len(raw)>5000,"native GLB unexpectedly empty")
    (out/"machine.glb").write_bytes(raw)
    record={"schema_version":"hardware_splicer.teardown_native_assembly_mesh.v1",
            "product_id":manifest["product_id"],"source_spec_sha256":manifest["source_spec_sha256"],
            "cadclaw_native_step_sha256":digest(assembly.read_bytes()),
            "glb_sha256":digest(raw),"parts":report,
            "source_geometry":"tessellated actual CADCLAW assembly STEP, independent solid identity via geometry",
            "native_cad_geometry_preserved":True,
            "real_mechanism_motion":False,"physical_release_authorized":False}
    (out/"ASSEMBLY_MESH_EVIDENCE.json").write_bytes(canonical(record))
    return record
