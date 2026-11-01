"""Render real HS STEP part topology in a sourced Teardown viewer.

The step->triangles conversion uses native CadQuery's OCC tessellator and
trimesh's glTF exporter. Assembly placement is resolved from the CADCLAW
native *reviewed concept* spec (frame-locked tray/panel plus explicit
transforms), not fabricated joints. Never claim measured physics.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .multicad_toolchain import canonical, digest, require
from .teardown_product import source_model

SCHEMA = "hardware_splicer.teardown_cad_showcase.v1"


def safe_vec(values: Any) -> list[float]:
    require(isinstance(values, list) and len(values) == 3
            and all(isinstance(v, (int,float)) and not isinstance(v,bool)
                    and math.isfinite(v) and abs(v) <= 1e5 for v in values),
            "unsafe CAD frame position")
    return [float(v) for v in values]


def resolve_positions(assembly: dict, connectors: dict, part_ids: set[str]) -> dict[str,list[float]]:
    require(assembly.get("schema_version") == "assembly_spec.v0.1"
            and connectors.get("schema_version") == "connector_metadata.v0.1",
            "unknown CADCLAW assembly metadata schema")
    instances = assembly.get("instances", [])
    require(len(instances) == len(part_ids) and {i.get("id") for i in instances} == part_ids,
            "assembly part inventory differs from STEP product")
    frames = {}
    for component in connectors.get("components", []):
        ident = component.get("id")
        require(ident in part_ids and ident not in frames, "unknown/duplicate connector identity")
        frames[ident]={}
        for entry in component.get("frames", []):
            require(entry.get("verified") is True, "unverified assembly connector datum")
            fid=entry.get("id")
            require(isinstance(fid,str) and fid not in frames[ident],"duplicate connector frame")
            frames[ident][fid]=safe_vec(entry.get("origin_mm"))
    lookup={i["id"]:i for i in instances}
    result={}
    visiting=set()
    def locate(ident):
        if ident in result: return result[ident]
        require(ident not in visiting,"cyclic assembly constraints")
        visiting.add(ident)
        instance=lookup[ident]
        if "place_relative_to" in instance:
            rel=instance["place_relative_to"]
            parent=rel.get("ref")
            require(parent in lookup and parent!=ident
                    and rel.get("lock")=="frame"
                    and rel.get("axis")=="z"
                    and rel.get("side")=="positive"
                    and float(rel.get("offset_mm",999))==0,
                    "unsupported or unqualified CADCLAW mating constraint")
            pf=frames.get(parent,{}).get(rel.get("parent_frame"))
            cf=frames.get(ident,{}).get(rel.get("frame"))
            require(pf is not None and cf is not None,
                    "missing source-validated connector transforms")
            p=locate(parent)
            translated=[p[i]+pf[i]-cf[i] for i in range(3)]
        else:
            value=instance.get("transform",{})
            require(set(value)=={"translate_mm"}, "unsupported CADCLAW rotation/scale")
            translated=safe_vec(value["translate_mm"])
        visiting.remove(ident)
        return result.setdefault(ident, translated)
    for ident in sorted(part_ids): locate(ident)
    return result


def create(multicad: Path, cadclaw: Path, output: Path) -> dict:
    import cadquery as cq
    import numpy as np
    import trimesh
    import yaml

    mc=Path(multicad)
    cr=Path(cadclaw)
    root=Path(output)
    require(not root.exists() or (root.is_dir() and not any(root.iterdir())),
            "refusing to overwrite existing frontend outputs")
    product=source_model(mc)
    manifest=json.loads((mc/"PARTS_MANIFEST.json").read_text())
    native=json.loads((cr/"CADCLAW_NATIVE_ASSEMBLY_EVIDENCE.json").read_text())
    source=json.loads((cr/"CADCLAW_INPUT_RECEIPT.json").read_text())
    assembly=yaml.safe_load((cr/"assembly.yaml").read_text())
    connectors=yaml.safe_load((cr/"connectors.yaml").read_text())
    ids={p["id"] for p in product["parts"]}
    require(native.get("schema_version")=="hardware_splicer.cadclaw_native_dry_assembly.v1"
            and native.get("source_spec_sha256")==product["source_spec_sha256"]
            and native.get("product_id")==product["product_id"]
            and native.get("manufacturing_authorized") is False
            and native.get("water_operation_authorized") is False
            and source.get("source_spec_sha256")==product["source_spec_sha256"]
            and source.get("physical_release_authorized") is False,
            "different or promoted CADCLAW assembly")
    combined=cr/"clearbench_s1_dry_reference.step"
    require(combined.is_file() and digest(combined.read_bytes())==
            native.get("cadclaw_native_assembly_step_sha256"),
            "CADCLAW actual assembly STEP was changed or missing")
    # The filename is the current CADCLAW backend artifact, not an assumption
    # about arbitrary manufacturer STEP designs in the viewer itself.
    placements=resolve_positions(assembly, connectors, ids)
    source_parts={p["id"]:p for p in manifest["parts"]}
    scene=trimesh.Scene()
    output_parts=[]
    global_mins=[]
    global_maxs=[]
    for part in product["parts"]:
        ident=part["id"]
        record=source_parts[ident]
        path=mc/"partcad"/"parts"/(ident+".step")
        require(digest(path.read_bytes())==part["authored_step_sha256"],
                "native authoring source changed")
        native_step=cq.importers.importStep(str(path))
        require(len(native_step.solids().vals())==1,
                "non-single-solid CAD not yet qualified for viewer")
        solid=native_step.solids().val()
        vertices,faces=solid.tessellate(0.35,0.15)
        points=np.array([v.toTuple() for v in vertices],dtype=float)
        triangles=np.array(faces,dtype=int)
        require(len(points)>=8 and len(triangles)>=12
                and np.isfinite(points).all()
                and int(triangles.min())>=0 and int(triangles.max())<len(points),
                "native OCC STEP tessellation did not produce valid triangles")
        mesh=trimesh.Trimesh(vertices=points,faces=triangles,process=True)
        require(mesh.is_watertight and mesh.is_volume and mesh.volume>0,
                "non-closed or invalid source-derived STEP tessellation")
        bb=mesh.bounds
        dim=bb[1]-bb[0]
        expected=np.array(part["extents_mm"])
        require(np.allclose(dim,expected,atol=0.4,rtol=0.0),
                "real STEP mesh dimensions disagree with native CAD evidence")
        # Tessellation only approximates a smooth cylinder. Check meaningful
        # geometric parity, not exact equality between BRep and triangle volume.
        solid_volume=solid.Volume()
        require(abs(mesh.volume-solid_volume)/solid_volume<=0.025,
                "OCC tessellation differs too far from real STEP solid")
        offset=np.array(placements[ident])
        matrix=np.eye(4)
        matrix[:3,3]=offset
        scene.add_geometry(mesh,node_name=ident,geom_name=ident,transform=matrix)
        global_mins.append(bb[0]+offset)
        global_maxs.append(bb[1]+offset)
        output_parts.append({
            **part,
            "translation_mm":placements[ident],
            "mesh_vertices":len(mesh.vertices),"mesh_triangles":len(mesh.faces),
            "mesh_volume_mm3":round(float(mesh.volume),3),
            "native_step_volume_mm3":round(float(solid_volume),3),
            "source_step_verified":True,
            "source_assembly_constraint":bool(
                next(x for x in assembly["instances"] if x["id"]==ident).get("place_relative_to")),
        })
    lower=np.min(np.array(global_mins),axis=0)
    upper=np.max(np.array(global_maxs),axis=0)
    bbox=upper-lower
    require(np.allclose(bbox,native["assembly_bbox_mm"],atol=0.65,rtol=0.0),
            "placed mesh bounds do not match independently verified CADCLAW assembly")
    glb=scene.export(file_type="glb")
    require(isinstance(glb,bytes) and len(glb)>1024, "native GLB exporter failed")
    root.mkdir(parents=True,exist_ok=True)
    source_template=Path(__file__).resolve().parents[2]/"assets/teardown/hs_cad_showcase_main.js"
    template=source_template.read_text()
    token="__HS_SHOWCASE_MODEL_JSON__"
    require(template.count(token)==1, "invalid frontend template marker")
    payload={
        "schema_version":SCHEMA,
        "product_id":product["product_id"],
        "source_spec_sha256":product["source_spec_sha256"],
        "cadclaw_assembly_step_sha256":native["cadclaw_native_assembly_step_sha256"],
        "native_source":"CADCLAW + build123d + CadQuery / OCC STEP tessellation",
        "glb_sha256":digest(glb),
        "real_step_surface_geometry":True,
        "assembled_transform_source":"CADCLAW assembly_spec.v0.1 + reviewed connector frames",
        "assembly_bounds_mm":[round(float(v),3) for v in bbox],
        "assembly_center_mm":[round(float(v),3) for v in (lower+upper)/2],
        "parts":output_parts,
        "visualization_only":True,
        "physical_fit_verified":False,
        "real_operation_simulated":False,
        "fabrication_authorized":False,
    }
    folder=root/"machine"
    folder.mkdir()
    (folder/"machine.glb").write_bytes(glb)
    # JSX-like text is never interpolated from untrusted product information.
    embedded=json.dumps(payload,sort_keys=True,ensure_ascii=True).replace("</","<\\/")
    (folder/"main.js").write_text(template.replace(token,embedded))
    (root/"SHOWCASE_INPUT.json").write_bytes(canonical(payload))
    receipt={
        "schema_version":"hardware_splicer.teardown_cad_showcase_receipt.v1",
        "source_spec_sha256":payload["source_spec_sha256"],
        "product_id":payload["product_id"],
        "glb_sha256":digest(glb),
        "main_js_sha256":digest((folder/"main.js").read_bytes()),
        "input_sha256":digest((root/"SHOWCASE_INPUT.json").read_bytes()),
        "part_count":len(output_parts),
        "browser_verified":False,
        "physical_kinematics_verified":False,
        "release_authorized":False,
    }
    (root/"SHOWCASE_RECEIPT.json").write_bytes(canonical(receipt))
    return receipt
