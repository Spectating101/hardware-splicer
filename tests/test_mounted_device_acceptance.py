"""Synthetic negative tests of mount acceptance (native CAD is tested in CI)."""
import hashlib
import json
import math
from pathlib import Path

import pytest

from hardware_splicer.mounted_device_acceptance import assess_native_mounted_reference
from hardware_splicer.pcb_mounting_cad import generate_pcb_mounted_shell

ROOT=Path(__file__).resolve().parents[1]
PCB=ROOT/"hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_pcb"
SEED=ROOT/"examples/external_engines/cad/spi_adapter_shell.json"


def digest(data):
    return "sha256:"+hashlib.sha256(data).hexdigest()


def fixture(tmp_path):
    mounted=tmp_path/"mounted"
    native=tmp_path/"native"
    (native/"mounted_shell").mkdir(parents=True)
    (native/"mounted_shell_measurement").mkdir()
    recipe=mounted/"script.json"
    req=mounted/"manifest.json"
    manifest=generate_pcb_mounted_shell(
        pcb_path=PCB,seed_recipe_path=SEED,
        output_recipe_path=recipe,output_manifest_path=req)
    model=b"ISO-10303-21;\nSYNTHETIC-NOT-REAL-CAD\nEND-ISO-10303-21;"
    step=native/"mounted_shell/model.step"
    step.write_bytes(model)
    volume=39412+4*(math.pi*3.3**2*3.2-math.pi*1.65**2*5.2)
    measured={"shape_valid":True,"solid_count":1,
              "volume_mm3":volume,"bbox_mm":[110,70,25]}
    measured_file=native/"mounted_shell_measurement/step_inspection.json"
    measured_file.write_text(json.dumps(measured))
    report={"schema":"hardware_splicer.external_engine_execution.v1",
            "completed":2,"blocked":0,"fabrication_authorized":False,
            "tasks":[
                {"id":"mounted_shell","engine":"solidcraft",
                 "status":"tool_passed_artifact_observed",
                 "source_sha256":digest(recipe.read_bytes()),
                 "artifacts":[{"sha256":digest(model)}]},
                {"id":"mounted_shell_measurement","engine":"freecad",
                 "status":"tool_passed_artifact_observed",
                 "source_sha256":digest(model),
                 "artifacts":[{"sha256":digest(measured_file.read_bytes())}]}
            ]}
    (native/"ENGINE_ORCHESTRATION_REPORT.json").write_text(json.dumps(report))
    samples=[
        {"ref":"shell","kind":"floor_center","sample_xyz_mm":[55,35,1],"expected_material":True,"measured_material":True,"pass":True},
        {"ref":"shell","kind":"open_cavity","sample_xyz_mm":[55,35,12],"expected_material":False,"measured_material":False,"pass":True},
    ]
    for mount in manifest["mounts"]:
        x,y=mount["cad_shell_center_xy_mm"]
        for kind,coord,mat in [
            ("boss_annulus",[x+2.4,y,4],True),
            ("pilot_hole",[x,y,4],False),
            ("floor_through_hole",[x,y,1],False),
        ]:
            samples.append({"ref":mount["ref"],"kind":kind,"sample_xyz_mm":coord,
                            "expected_material":mat,"measured_material":mat,"pass":True})
    topo={
        "schema":"hardware_splicer.native_mounted_shell_topology.v1",
        "source_step_sha256":digest(model),
        "source_mount_manifest_sha256":digest(req.read_bytes()),
        "source_kicad_sha256":digest(PCB.read_bytes()),
        "engine":"FreeCAD Part.Shape.isInside",
        "shape_valid":True,"solid_count":1,"volume_mm3":volume,
        "expected_volume_mm3":volume,"checks_passed":True,
        "sample_checks":samples,
        "fabrication_authorized":False,"release_authorized":False,
    }
    topology=native/"MOUNTED_SHELL_TOPOLOGY.json"
    topology.write_text(json.dumps(topo))
    return recipe,req,native,topology


def assess(tmp_path,paths):
    recipe,req,native,_=paths
    return assess_native_mounted_reference(
        pcb_path=PCB,seed_path=SEED,
        mounted_recipe_path=recipe,mounting_manifest_path=req,
        native_engine_dir=native,output_dir=tmp_path/"assessed")


def test_synthetic_fixture_proves_acceptance_contract_only(tmp_path):
    paths=fixture(tmp_path)
    result=assess(tmp_path,paths)
    assert result["status"]=="native_boss_and_bore_geometry_validated_assembly_unverified"
    assert result["mount_count"]==4 and result["native_3d_material_void_checks"]==14
    assert result["source_pcb_envelope_blockers"]==0
    assert not result["release_authorized"]
    assert (tmp_path/"assessed/MOUNTED_DEVICE_REVIEW.json").is_file()


def test_fake_hole_void_cannot_pass_report_flag(tmp_path):
    paths=fixture(tmp_path)
    topo=paths[-1]
    data=json.loads(topo.read_text())
    data["sample_checks"][3]["measured_material"]=True
    topo.write_text(json.dumps(data))
    with pytest.raises(ValueError,match="sample mismatch"):
        assess(tmp_path,paths)


def test_stale_cad_or_modified_recipe_cannot_reuse_old_proof(tmp_path):
    paths=fixture(tmp_path)
    recipe=paths[0]
    recipe.write_text(recipe.read_text()+"\n")
    with pytest.raises(ValueError,match="hash mismatch"):
        assess(tmp_path,paths)


def test_replayed_step_export_rejected_if_freecad_saw_different_bytes(tmp_path):
    paths=fixture(tmp_path)
    native=paths[2]
    path=native/"ENGINE_ORCHESTRATION_REPORT.json"
    report=json.loads(path.read_text())
    report["tasks"][1]["source_sha256"]=digest(b"wrong-step")
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError,match="lineage"):
        assess(tmp_path,paths)
