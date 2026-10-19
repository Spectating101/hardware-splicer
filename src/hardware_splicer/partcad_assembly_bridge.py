"""Source-linked SolidCraft STEP -> PartCAD package, without hardware claims.

This adapter writes the bounded, well-defined file interoperability layer.
It does NOT call hardware, assert donor identity, or run PartCAD's compiler.
Native PartCAD CLI integration and return-geometry checks are separate.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

SCHEMA="hardware_splicer.partcad_assembly_handoff.v1"
_PART = re.compile(r"^[a-z][a-z0-9_]{2,54}$")


def _hash(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_partcad_assembly_package(
    *,
    solidcraft_step: Path,
    destination:Path,
    part_id:str="concept_envelope",
    assembly_id:str="conceptual_station",
    source_kind:str="declared_concept_fixture",
    declared_envelope_mm:dict[str,float]|None=None,
)->dict[str,Any]:
    """Build PartCAD YAML + assembly + provenance. No stock or physical approval."""
    if source_kind!="declared_concept_fixture":
        raise ValueError("No independently authenticated physical specimen; only declared concept fixtures allowed")
    if not (_PART.fullmatch(part_id) and _PART.fullmatch(assembly_id)) or part_id==assembly_id:
        raise ValueError("Invalid or duplicated part/assembly identifier")
    step=Path(solidcraft_step).resolve(strict=True)
    if not step.is_file() or step.suffix.lower()!=".step" or not 128<=step.stat().st_size<=16_000_000:
        raise ValueError("Input must be a bounded existing STEP file")
    if "ISO-10303-21" not in step.read_bytes()[:160].decode("latin1"):
        raise ValueError("Unsupported STEP header")
    dims=declared_envelope_mm or {}
    if set(dims)!={"width","depth","height"} or any(
        isinstance(v,bool) or not isinstance(v,(float,int)) or not 1<=v<=2000 for v in dims.values()
    ):
        raise ValueError("Exactly three finite, explicitly declared positive envelope dimensions required")
    import math
    if any(not math.isfinite(v) for v in dims.values()):
        raise ValueError("Nonfinite geometric input")
    # Don't overwrite another package / suspicious existing files.
    destination=Path(destination).resolve()
    destination.mkdir(parents=True,exist_ok=True)
    for name in ("partcad.yaml","assembly.assy","source.step","HS_PARTCAD_AUTHORITY.json"):
        if (destination/name).exists():
            raise FileExistsError("Refuse to overwrite existing PartCAD case: "+name)
    copy=destination/"source.step"
    shutil.copyfile(step,copy)
    if _hash(copy)!=_hash(step):
        raise RuntimeError("Imported STEP differs from original source")
    # IDs are strictly bounded to prevent YAML injection.
    config=(
        "desc: Hardware Splicer declared concept fixture. Not a donor or production assembly.\n"
        "parts:\n"
        f"  {part_id}:\n"
        "    type: step\n"
        "    path: source.step\n"
        "    desc: Declared test geometry; source hash in HS_PARTCAD_AUTHORITY.json\n"
        "assemblies:\n"
        f"  {assembly_id}:\n"
        "    type: assy\n"
        "    path: assembly.assy\n"
        "    desc: Conditional conceptual layout only. Never physical stock.\n"
    )
    assembly=(
        "links:\n"
        f"  - part: {part_id}\n"
        f"    name: {part_id}_instance\n"
        "    description: Concept fixture; real fit, material, mounting and wiring unknown.\n"
        "    location: [[0, 0, 0], [0, 0, 1], 0]\n"
    )
    (destination/"partcad.yaml").write_text(config)
    (destination/"assembly.assy").write_text(assembly)
    record={
        "schema_version":SCHEMA,
        "partcad_project_kind":"CONDITIONAL_NONPHYSICAL_CONCEPT",
        "cad_backend":"SolidCraft",
        "package_backend":"PartCAD",
        "part_id":part_id,
        "assembly_id":assembly_id,
        "solidcraft_step_source_sha256":_hash(step),
        "partcad_source_step_sha256":_hash(copy),
        "declared_concept_envelope_mm":{k:float(v) for k,v in dims.items()},
        "source_kind":source_kind,
        "source_is_measured_salvage":False,
        "physical_specimen_id":None,
        "inventree_stock_item_id":None,
        "usable_quantity":0,
        "sourcing_confidence":"NOT_IN_POSSESSION",
        "electrical_interface_verified":False,
        "mechanical_fit_verified":False,
        "assembly_bom_is_a_design_not_stock":True,
        "physical_fabrication_authorized":False,
    }
    (destination/"HS_PARTCAD_AUTHORITY.json").write_text(json.dumps(record,indent=2,sort_keys=True)+"\n")
    return record


def verify_native_solidcraft_roundtrip(
    evaluation:dict[str,Any],declared_envelope_mm:dict[str,float]
)->dict[str,Any]:
    """Independently check actual SolidCraft eval output, not PartCAD pass flags.

    For the narrowly specified rectangular-box fixture only; this is NOT
    suitable for arbitrary donor meshes or a more complex assembly.
    """
    import math

    dims=[float(declared_envelope_mm[k]) for k in ("width","depth","height")]
    check=lambda a,b,tol=0.001: (
        type(a) in (int,float) and math.isfinite(a)
        and math.isclose(float(a),float(b),rel_tol=0,abs_tol=tol)
    )
    shapes=evaluation.get("bodies")
    errors=[]
    if not isinstance(shapes,list) or len(shapes)!=1:
        errors.append("expected_exactly_one_body")
    else:
        body=shapes[0]
        bbox=body.get("bbox") or {}
        for name,target in (("min",[0,0,0]),("max",dims)):
            observed=bbox.get(name)
            if not isinstance(observed,list) or len(observed)!=3 or not all(check(x,y) for x,y in zip(observed,target)):
                errors.append("bounding_box_"+name+"_mismatch")
        if not check(body.get("volume_mm3"),math.prod(dims),tol=0.01):
            errors.append("volume_mismatch")
        x,y,z=dims
        if not check(body.get("area_mm2"),2*(x*y+y*z+x*z),tol=0.01):
            errors.append("surface_area_mismatch")
        if body.get("faces")!=6 or body.get("edges")!=12:
            errors.append("expected_rectangular_prism_topology")
        center=body.get("center_of_mass")
        if not isinstance(center,list) or len(center)!=3 or not all(check(v,w/2) for v,w in zip(center,dims)):
            errors.append("center_of_mass_mismatch")
    return {
        "schema_version":"hardware_splicer.partcad_solidcraft_geometry_oracle.v1",
        "geometry_checked":not errors,
        "failed_checks":errors,
        "only_applies_to_declared_rectangular_concept":True,
        "physical_part_dimensions_authenticated":False,
        "physical_fabrication_authorized":False,
    }
