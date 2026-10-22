"""Verify source-linked four-M3 native shell with physical authority blocked."""
from __future__ import annotations
import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import Path

from .pcb_mounting_cad import generate_pcb_mounted_shell
from .reference_device_dossier import build_reference_device_dossier
from .connector_access_plan import inspect_connector_access
from .connector_mating_volume import inspect_mating_volume

SCHEMA="hardware_splicer.native_mounted_device_review.v1"

def _digest(blob:bytes)->str:
    return "sha256:"+hashlib.sha256(blob).hexdigest()


def assess_native_mounted_reference(*,pcb_path:str|Path,seed_path:str|Path,
                                    mounted_recipe_path:str|Path,
                                    mounting_manifest_path:str|Path,
                                    native_engine_dir:str|Path,
                                    output_dir:str|Path)->dict:
    source,seed=Path(pcb_path),Path(seed_path)
    generated,requirements=Path(mounted_recipe_path),Path(mounting_manifest_path)
    root,out=Path(native_engine_dir),Path(output_dir)
    if out.exists() and any(out.iterdir()):
        raise ValueError("native mounted device destination is not empty")
    raw_pcb=source.read_bytes()
    raw_generated=generated.read_bytes()
    raw_manifest=requirements.read_bytes()
    manifest=json.loads(raw_manifest)
    if manifest.get("schema")!="hardware_splicer.pcb_derived_mounting_cad.v1":
        raise ValueError("unknown KiCad mounting geometry manifest")
    if (manifest.get("input_pcb_sha256")!=_digest(raw_pcb)
            or manifest.get("input_shell_seed_sha256")!=_digest(seed.read_bytes())
            or manifest.get("generated_solidcraft_script_sha256")!=_digest(raw_generated)):
        raise ValueError("KiCad mount source/recipe hash mismatch")
    # Reproduce expected CAD source independently from the original PCB and
    # baseline shell; this prevents copied or stale four-mount source manifests.
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as temporary:
        temporary=Path(temporary)
        recreated=generate_pcb_mounted_shell(
            pcb_path=source,seed_recipe_path=seed,
            output_recipe_path=temporary/"expected.json",
            output_manifest_path=temporary/"expected_manifest.json")
        if recreated!=manifest or (temporary/"expected.json").read_bytes()!=raw_generated:
            raise ValueError("native mounted CAD script differs from deterministic KiCad output")
    native=json.loads((root/"ENGINE_ORCHESTRATION_REPORT.json").read_text())
    if native.get("schema")!="hardware_splicer.external_engine_execution.v1":
        raise ValueError("missing native engine execution schema")
    if native.get("completed")!=2 or native.get("blocked")!=0:
        raise ValueError("native CAD engine stages incomplete")
    task=native.get("tasks")
    if not isinstance(task,list) or len(task)!=2 or [
        (item.get("id"),item.get("engine"),item.get("status"))
        for item in task if isinstance(item,Mapping)
    ]!=[
        ("mounted_shell","solidcraft","tool_passed_artifact_observed"),
        ("mounted_shell_measurement","freecad","tool_passed_artifact_observed"),
    ]:
        raise ValueError("native CAD provider identity mismatch")
    if task[0].get("source_sha256")!=_digest(raw_generated):
        raise ValueError("SolidCraft consumed different KiCad-generated recipe")
    model=(root/"mounted_shell/model.step").read_bytes()
    if not model.lstrip().startswith(b"ISO-10303-21;"):
        raise ValueError("SolidCraft model is not STEP")
    step_sha=_digest(model)
    measured_bytes=(root/"mounted_shell_measurement/step_inspection.json").read_bytes()
    measured=json.loads(measured_bytes)
    def contains_digest(row:dict,sha:str):
        return any(isinstance(a,Mapping) and a.get("sha256")==sha for a in row.get("artifacts",[]))
    if (not contains_digest(task[0],step_sha)
            or task[1].get("source_sha256")!=step_sha
            or not contains_digest(task[1],_digest(measured_bytes))):
        raise ValueError("native STEP-to-FreeCAD artifact lineage failed")
    topo_bytes=(root/"MOUNTED_SHELL_TOPOLOGY.json").read_bytes()
    topology=json.loads(topo_bytes)
    count=2+3*manifest["mount_count"]
    samples=topology.get("sample_checks")
    if (topology.get("schema")!="hardware_splicer.native_mounted_shell_topology.v1"
            or topology.get("source_step_sha256")!=step_sha
            or topology.get("source_mount_manifest_sha256")!=_digest(raw_manifest)
            or topology.get("source_kicad_sha256")!=_digest(raw_pcb)
            or topology.get("engine")!="FreeCAD Part.Shape.isInside"
            or topology.get("checks_passed") is not True
            or topology.get("shape_valid") is not True
            or topology.get("solid_count")!=1
            or not isinstance(samples,list) or len(samples)!=count
            or any(item.get("pass") is not True for item in samples)):
        raise ValueError("actual native mounting bore/boss topology not verified")
    expected_samples=[
        ("shell","floor_center",[55,35,1],True),
        ("shell","open_cavity",[55,35,12],False),
    ]
    for mount in manifest["mounts"]:
        x,y=mount["cad_shell_center_xy_mm"]
        expected_samples.extend([
            (mount["ref"],"boss_annulus",[x+2.4,y,4],True),
            (mount["ref"],"pilot_hole",[x,y,4],False),
            (mount["ref"],"floor_through_hole",[x,y,1],False),
        ])
    for sample,(ref,kind,location,occupied) in zip(samples,expected_samples):
        if (not isinstance(sample,Mapping) or sample.get("ref")!=ref
                or sample.get("kind")!=kind
                or sample.get("sample_xyz_mm")!=location
                or sample.get("expected_material") is not occupied
                or sample.get("measured_material") is not occupied
                or sample.get("pass") is not True):
            raise ValueError("native mounting hole/boss topology sample mismatch")
    if (not isinstance(measured.get("bbox_mm"),list)
            or len(measured["bbox_mm"])!=3
            or any(abs(float(a)-b)>0.02 for a,b in zip(measured["bbox_mm"],(110,70,25)))):
        raise ValueError("native mounted shell outer bounds mismatch")
    if measured.get("shape_valid") is not True or measured.get("solid_count")!=1:
        raise ValueError("independent FreeCAD measurement invalid")
    if abs(float(measured.get("volume_mm3",0))-float(topology["volume_mm3"]))>0.1:
        raise ValueError("native CAD volume measurements disagree")
    if abs(float(topology["volume_mm3"])-float(topology["expected_volume_mm3"]))>0.1:
        raise ValueError("native CAD does not match hole/boss material volume")
    if any(native.get(k) is True or topology.get(k) is True for k in
           ("fabrication_authorized","power_on_authorized","release_authorized")):
        raise ValueError("false physical authority claim")
    out.mkdir(parents=True,exist_ok=True)
    original=build_reference_device_dossier(
        source,output_dir=out/"electrical",
        declared_internal_enclosure_mm={"w":104,"d":64,"h":23})
    fit=original["electromechanical_fit"]
    if fit is None or fit["blocker_count"]!=0:
        raise ValueError("native mounted shell does not screen-clear source PCB")
    # A top-open vertical header has no side cutout requirement. However,
    # the exact KiCad courtyard and source pin positions must project into
    # the actual cavity without colliding with the source-driven bosses.
    access = inspect_connector_access(
        pcb_path=source,
        mounting_manifest_path=requirements,
        output_path=out/"CONNECTOR_ACCESS_REVIEW.json",
    )
    if access["status"] != "nominal_open_top_projection_clear_unverified":
        raise ValueError("source connector access conflicts with cavity or mounting bosses")
    # Qualify the *known* male Samtec headers separately from the unknown
    # female plug/cable. An open-top clearance result can never authorize
    # physical mating or call the shell a finished assembly.
    mating = inspect_mating_volume(
        pcb_path=source,
        bom_path=source.parent/"BOM.csv",
        mounting_manifest_path=requirements,
        output_path=out/"CONNECTOR_MATING_VOLUME.json",
    )
    if mating["status"] == "blocked_nominal_3d_insertion_geometry":
        raise ValueError("3D header insertion volume intersects a modeled obstacle")
    native_mating_collision = None
    native_probe_path = root/"NATIVE_MATING_COLLISION.json"
    if native_probe_path.is_file():
        native_mating_collision = json.loads(native_probe_path.read_text())
        actual_mating_hash = _digest((out/"CONNECTOR_MATING_VOLUME.json").read_bytes())
        required = (
            native_mating_collision.get("schema") ==
                "hardware_splicer.native_connector_access_collision.v1"
            and native_mating_collision.get("engine")=="FreeCAD Part.Shape.common"
            and native_mating_collision.get("source_step_sha256")==step_sha
            and native_mating_collision.get("source_connector_report_sha256")==actual_mating_hash
            and native_mating_collision.get("shape_valid") is True
            and native_mating_collision.get("connector_count")==2
            and native_mating_collision.get("nominal_corridors_shell_clear") is True
            and isinstance(native_mating_collision.get("checks"),list)
            and {r.get("ref") for r in native_mating_collision["checks"]}=={"J1","JP1"}
            and all(r.get("no_shell_material_in_access_corridor") is True
                    and float(r.get("clash_volume_mm3",1))<0.001
                    for r in native_mating_collision["checks"])
        )
        if not required:
            raise ValueError("native STEP connector corridor intersections missing or invalid")
    result={
        "schema":SCHEMA,
        "status":"native_boss_and_bore_geometry_validated_assembly_unverified",
        "pcb_source_sha256":_digest(raw_pcb),
        "mount_script_sha256":_digest(raw_generated),
        "native_step_sha256":step_sha,
        "topology_report_sha256":_digest(topo_bytes),
        "mounts":manifest["mounts"],
        "mount_count":manifest["mount_count"],
        "native_3d_material_void_checks":count,
        "source_pcb_envelope_blockers":fit["blocker_count"],
        "connector_access_status":access["status"],
        "connector_count":access["connector_count"],
        "connector_access_sha256":_digest((out/"CONNECTOR_ACCESS_REVIEW.json").read_bytes()),
        "connector_mating_status":mating["status"],
        "connector_mating_report_sha256":_digest((out/"CONNECTOR_MATING_VOLUME.json").read_bytes()),
        "native_connector_shell_collision_checked":native_mating_collision is not None,
        "native_connector_shell_collision_report_sha256":(
            _digest(native_probe_path.read_bytes()) if native_mating_collision is not None else None
        ),
        "counterpart_harness_selected":False,
        "source_pcb_nominal_support_height_mm":5.2,
        "fastener_mechanics_verified":False,
        "connector_mating_or_access_verified":False,
        "nominal_open_top_connector_projection_checked":True,
        "PCB_physically_fitted":False,
        "fabrication_authorized":False,
        "power_on_authorized":False,
        "release_authorized":False,
        "next_actions":[
            "Check exact screw/washer dimensions, insulation and printed boss tolerances",
            "Select and authenticate a real mating female header/cable assembly; verify plug body, bend radius and service insertion",
            "Run exact 3D STEP-vs-board-body intersection rather than nominal courtyard screens",
            "Independent EE/manufacturer review and controlled physical assembly"
        ],
    }
    (out/"MOUNTED_DEVICE_REVIEW.json").write_text(
        json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    return result
