#!/usr/bin/env python3
"""Real upstream OpenArm URDF -> existing HS robot engineering project + original viewer.

No 3D viewer, kinematics engine, CAD kernel or source robotics model is recreated.
This script uses existing hardware_splicer.robot_model_import and
robot_machine_projection. It preserves separate source-revision identities:
the public OpenArm v1.0 URDF is NOT declared exactly equivalent to the
independent v1.1 OpenArm CAD Explorer assembly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from hardware_splicer.machine_project import MachineProject, ReleaseState, ArtifactRef, AuthorityState
from hardware_splicer.robot_model_import import parse_robot_model, topology_from_robot_model
from hardware_splicer.robot_machine_projection import project_robot_topology

SCHEMA="hardware_splicer.upstream_robot_capability_handoff.v1"
MODEL_REF="2e27c793e10aa2045e7eb597b9b9b9dc08fb0a08"
MODEL_URL="https://github.com/enactic/openarm_description"
MODEL_PATH="assets/robot/openarm_v1.0/urdf/example/v1.urdf"
VIEWER_REF="0c0852bd76ee7026f97875d6eac789d189a0012a"
VIEWER_URL="https://github.com/Utsav92/openarm-3d-cad-assembly"


def check(ok:bool,msg:str)->None:
    if not ok:raise ValueError("Upstream capability import refused: "+msg)


def sha(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()


def write_json(path:Path,value:dict)->None:
    path.write_text(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n")


def execute(urdf:Path,upstream_viewer:Path,output:Path)->dict:
    out=Path(output)
    check(not out.exists() or (out.is_dir() and not any(out.iterdir())),
          "will not overwrite existing engineering artifacts")
    raw=Path(urdf).read_bytes()
    check(len(raw)>15000 and len(raw)<5*1024*1024,
          "expected complete source URDF artifact, not a fake minimal geometry")
    check(b"openarm" in raw.lower(),"wrong manufacturer robot description")
    viewer=Path(upstream_viewer)
    manifest=json.loads((viewer/"manifest.json").read_text())
    check(manifest.get("schema_version")=="hardware_splicer.upstream_viewer_adapter.v1"
          and manifest.get("upstream_ref")==VIEWER_REF
          and manifest.get("viewer_origin")=="upstream_unmodified"
          and manifest.get("geometry_authored_by_hs") is False
          and manifest.get("physical_motion_verified") is False,
          "source original CAD viewer not packaged or falsely attributed")
    source_files=manifest.get("source_files",{})
    catalogs={}
    for arm,expected in (("follower",542),("leader",516)):
        name=f"models/{arm}_metadata.json"
        local=viewer/name
        check(local.is_file() and sha(local.read_bytes())==source_files[name]["sha256"],
              "original upstream component data changed")
        data=json.loads(local.read_text())
        check(len(data.get("parts",[]))==data.get("totalParts")==expected,
              "upstream CAD component inventory incomplete")
        ids=[row.get("node") for row in data["parts"]]
        check(all(isinstance(i,str) and i for i in ids) and len(set(ids))==expected,
              "upstream assembly has duplicate or missing CAD nodes")
        catalogs[arm]={
            "parts":expected,
            "categories":sorted(set(str(p.get("category") or "unknown") for p in data["parts"])),
            "subassemblies":sorted(set(str(p.get("subassembly") or "unknown") for p in data["parts"])),
            "node_ids":ids,
            "source_sha256":source_files[name]["sha256"],
        }
    parsed=parse_robot_model(raw,"urdf")
    check(len(parsed.links)>=20 and len(parsed.joints)>=20,
          "source robotics model missing its actual articulated topology")
    topology=topology_from_robot_model(parsed)
    project=MachineProject(
        project_id="openarm_v10_upstream_description_reference",
        name="OpenArm v1.0 — source-derived robotics engineering reference",
        purpose="Reuse official published articulated robot description in HS engineering graph; reference only.",
        requested_release_state=ReleaseState.CONCEPT,
        artifacts=[
            ArtifactRef(
                artifact_id="openarm-v10-official-urdf",
                kind="external_robot_description",
                ref=f"{MODEL_URL}/blob/{MODEL_REF}/{MODEL_PATH}",
                authority=AuthorityState.DECLARED,
                metadata={
                    "source_commit":MODEL_REF,"sha256":sha(raw),
                    "original_model_format":"urdf",
                    "physical_tested":False,
                },
            ),
            ArtifactRef(
                artifact_id="openarm-v11-original-cad-explorer",
                kind="external_cad_reference_viewer",
                ref=f"{VIEWER_URL}/tree/{VIEWER_REF}",
                authority=AuthorityState.DECLARED,
                metadata={
                    "source_commit":VIEWER_REF,"variant":"v1.1",
                    "same_revision_as_urdf":False,
                    "geometry_authored_by_hs":False,
                    "physical_tested":False,
                },
            ),
        ],
        metadata={
            "reference_only":True,
            "source_author":"Enactic, Inc.",
            "source_variant":"openarm_v1.0",
            "viewer_variant":"OpenArm v1.1 CAD Explorer",
            "same_revision_geometry_topology_binding_verified":False,
            "physical_authority_granted":False,
        },
    )
    projected=project_robot_topology(project,topology)
    check(projected.requested_release_state==ReleaseState.CONCEPT,
          "external source accidentally authorized fabrication")
    check(len(projected.components)>0 and len(projected.interfaces)>0,
          "existing HS projector did not connect the original robot topology")
    # Count model-derived parts, not pretend they are mechanically one-to-one
    # with the 542 source-viewer CAD solids.
    lineage={
        "schema_version":SCHEMA,
        "project_id":projected.project_id,
        "upstream_robot_description":{
            "repository":MODEL_URL,"commit":MODEL_REF,"path":MODEL_PATH,
            "format":"urdf","sha256":sha(raw),"license":"Apache-2.0",
            "published_links":len(parsed.links),"published_joints":len(parsed.joints),
            "published_actuators":len(parsed.actuators),
        },
        "upstream_cad_viewer":{
            "repository":VIEWER_URL,"commit":VIEWER_REF,
            "viewer_original":True,"follower_cad_parts":catalogs["follower"]["parts"],
            "leader_cad_parts":catalogs["leader"]["parts"],
            "hardware_license":"CERN-OHL-S-2.0",
            "viewer_license_reported_by_readme":"MIT",
        },
        "hs_native_projection":{
            "mechanical_components":len(projected.components),
            "interfaces":len(projected.interfaces),
            "subsystems":len(projected.subsystems),
            "unresolved_robot_fields":len(topology.unresolved),
            "source_parser":"hardware_splicer.robot_model_import.parse_robot_model",
            "source_projector":"hardware_splicer.robot_machine_projection.project_robot_topology",
            "new_robot_parser_written":False,
            "new_cad_viewer_written":False,
        },
        "reconciliation":{
            "same_source_revision":False,
            "same_assembly_topology_joined":False,
            "reason":"Official OpenArm v1.0 URDF and independent CAD Explorer v1.1 are different published variants; numeric component counts are not equivalent engineering identifiers.",
            "source_cad_parts_not_manufacturer_qualified_bom":True,
            "robot_motion_physically_verified":False,
            "fabrication_authorized":False,
        },
    }
    out.mkdir(parents=True)
    write_json(out/"OPENARM_URDF_TOPOLOGY.json",topology.model_dump(mode="json"))
    write_json(out/"OPENARM_MACHINE_PROJECT.json",projected.model_dump(mode="json"))
    write_json(out/"OPENARM_SOURCE_LINEAGE.json",lineage)
    write_json(out/"OPENARM_CAD_PART_CATALOG.json",{
        "schema_version":"hardware_splicer.upstream_cad_part_index.v1",
        "note":"Original CAD node IDs, not a qualified manufacturing BOM",
        "source_commit":VIEWER_REF,"variants":catalogs,
        "geometry_authored_by_hs":False,
    })
    (out/"README.md").write_text(
        "# OpenArm: actual upstream tools integrated into Hardware Splicer\n\n"
        f"- **Original full CAD viewer**: [{VIEWER_URL}]({VIEWER_URL}/tree/{VIEWER_REF}). "
        "The UI, GLB models, exploded views and part inspector are all upstream's; HS does not rewrite them.\n"
        f"- **Original robot URDF**: [{MODEL_PATH}]({MODEL_URL}/blob/{MODEL_REF}/{MODEL_PATH}). "
        "HS's existing URDF parser and robot-to-MachineProject projector reuse these actual published kinematic relationships.\n"
        f"- **Projected**: {len(parsed.links)} source links, {len(parsed.joints)} source joints "
        f"=> {len(projected.components)} canonical HS components and {len(projected.interfaces)} interfaces.\n"
        "- **IMPORTANT**: OpenArm v1.0 URDF is NOT asserted identical to the independent "
        "OpenArm v1.1 CAD viewer. CAD node IDs cannot be silently mapped to URDF link IDs. "
        "No build or motion authority; no fabricated product or vendor-qualified BOM.\n"
        "- **Next reuse target**: a single-version hardware asset with matching URDF, native CAD, "
        "real electrical design and manufacturer BOM for full subsystem reconciliation.\n"
    )
    return lineage


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--urdf",type=Path,required=True)
    p.add_argument("--upstream-viewer",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(execute(a.urdf,a.upstream_viewer,a.output),indent=2))
