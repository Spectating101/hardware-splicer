"""Adversarial contract checks with synthetic receipts.

Synthetic fixtures test the verifier only; they are explicitly *not*
a substitute for the native-toolchain CI artifacts.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import pytest
from hardware_splicer.engineering_acceptance_sensor import validate_evidence

def sha(body):
    return hashlib.sha256(body).hexdigest()

def put(root,name,data):
    file=root/name
    file.parent.mkdir(parents=True,exist_ok=True)
    if isinstance(data,dict):
        data=(json.dumps(data,sort_keys=True)+"\n").encode()
    file.write_bytes(data)
    return {"sha256":sha(data),"bytes":len(data)}

def fake_receipts(tmp_path):
    geom=tmp_path/"geometry"
    firm=tmp_path/"firmware"
    geom.mkdir(parents=True)
    firm.mkdir(parents=True)
    spec={"modules":[{"id":"esp32"},{"id":"bme280"}]}
    plan={"modules":[{"id":"esp32"},{"id":"bme280"}]}
    inputs={
        "DEVICE_SPEC.json":put(geom,"DEVICE_SPEC.json",spec),
        "DEVICE_PLAN.json":put(geom,"DEVICE_PLAN.json",plan),
        "FIRMWARE_SOURCE.zip":put(geom,"FIRMWARE_SOURCE.zip",b"standin-for-source-zip"),
        "ENCLOSURE_INPUT.json":put(geom,"ENCLOSURE_INPUT.json",{}),
        "VENTILATION_PLAN.json":put(geom,"VENTILATION_PLAN.json",{}),
        "enclosure.scad":put(geom,"enclosure.scad",b"module geometry(){}"),
    }
    receipt={
      "schema_version":"hardware_splicer.cross_domain_sensor_001.v1",
      "source_spec_sha256":inputs["DEVICE_SPEC.json"]["sha256"],
      "revision_consistent":True,
      "artifacts":inputs,
      "fabrication_authorized":False,"flashing_authorized":False,
      "power_on_authorized":False,"device_physically_assembled":False,
      "hardware_measurements_present":False,
    }
    for root in (geom,firm):
        put(root,"CROSS_DOMAIN_RECEIPT.json",receipt)
    mesh={"watertight":True,"consistent_winding":True}
    base=put(geom,"enclosure_base.stl",b"valid-mesh-by-external-check")
    lid=put(geom,"enclosure_lid.stl",b"lid-native-mesh-proof")
    put(geom,"GEOMETRY_EVIDENCE.json",{
       "schema_version":"hardware_splicer.cross_domain_geometry_evidence.v1",
       "source_spec_sha256":receipt["source_spec_sha256"],
       "checked_source_artifact_hashes":True,
       "usb_opening":{"observed_3d_subtraction":True},
       "ventilation_openings":{"vent_cuts_independently_verified":True,"ambient_airflow_performance_verified":False},
       "physical_fit_verified":False,"manufacturing_authorized":False,
       "base":{**mesh,**base},"lid":{**mesh,**lid},
    })
    plan={"board_mounting":{"status":"BLOCKED_UNVERIFIED_BOARD_MOUNT_HOLES"}}
    planfile=put(geom,"LID_RETENTION_PLAN.json",plan)
    scad=put(geom,"enclosure_retained.scad",b"native fastening source")
    retbase=put(geom,"retained_base.stl",b"native rendered fastening mesh A")
    retlid=put(geom,"retained_lid.stl",b"native rendered fastening mesh B")
    put(geom,"LID_RETENTION_GEOMETRY_EVIDENCE.json",{
        "schema_version":"hardware_splicer.lid_retention_mesh_evidence.v1",
        "source_spec_sha256":receipt["source_spec_sha256"],
        "lid_retention_plan_sha256":planfile["sha256"],
        "geometry_source_sha256":scad["sha256"],
        "retention_ear_and_hole_geometry_verified":True,
        "board_mounting_verified":False,
        "physical_fit_verified":False,"assembly_authorized":False,"manufacturing_authorized":False,
        "retained_base":{**mesh,**retbase},"retained_lid":{**mesh,**retlid},
    })
    log=put(firm,"PLATFORMIO_COMPILE.log",b"BUILD SUCCESS")
    binary=put(firm,"platformio-application/.pio/build/application/firmware.bin",b"firmware-bin")
    elf=put(firm,"platformio-application/.pio/build/application/firmware.elf",b"firmware-elf")
    put(firm,"FIRMWARE_TARGET_COMPILE_EVIDENCE.json",{
        "schema_version":"hardware_splicer.cross_domain_target_compile.v1",
        "source_spec_sha256":receipt["source_spec_sha256"],
        "firmware_source_zip_sha256":inputs["FIRMWARE_SOURCE.zip"]["sha256"],
        "compile_pass":True,"exit_code":0,
        "toolchain":"PlatformIO Core, version 6.1.18",
        "command":["pio","run","--environment","application","--jobs","2"],
        "compile_log_sha256":log["sha256"],
        "compiled_artifacts":{"firmware.bin":binary,"firmware.elf":elf},
        "real_hardware_flashing":False,"physical_behavior_verified":False,
        "firmware_authorized":False,"power_on_authorized":False,
    })
    return geom,firm


def test_acceptance_consistent_evidence_contract_without_claiming_physical(tmp_path):
    g,f=fake_receipts(tmp_path)
    report,atlas=validate_evidence(g,f)
    assert report["cross_domain_consistency_pass"]
    assert report["release_readiness"]=="software_candidate_only"
    assert len(report["artifact_hashes_verified"])>=12
    assert atlas["atlas_runtime_required"] is False
    assert atlas["authorization"]["real_world_actuation"] is False

def test_refuse_stale_firmware_job_revision(tmp_path):
    g,f=fake_receipts(tmp_path)
    file=f/"CROSS_DOMAIN_RECEIPT.json"
    r=json.loads(file.read_text())
    r["source_spec_sha256"]="a"*64
    put(f,"CROSS_DOMAIN_RECEIPT.json",r)
    with pytest.raises(ValueError,match="different source receipts"):
        validate_evidence(g,f)

def test_refuse_mutated_mesh_or_binary(tmp_path):
    g,f=fake_receipts(tmp_path)
    (g/"retained_base.stl").write_bytes(b"modified")
    with pytest.raises(ValueError,match="SHA256 mismatch"):
        validate_evidence(g,f)
    g,f=fake_receipts(tmp_path/"next")
    (f/"platformio-application/.pio/build/application/firmware.bin").write_bytes(b"modified")
    with pytest.raises(ValueError,match="SHA256 mismatch"):
        validate_evidence(g,f)

def test_refuse_failed_compile_or_false_authority(tmp_path):
    g,f=fake_receipts(tmp_path)
    file=f/"FIRMWARE_TARGET_COMPILE_EVIDENCE.json"
    body=json.loads(file.read_text())
    body["compile_pass"]=False
    put(f,"FIRMWARE_TARGET_COMPILE_EVIDENCE.json",body)
    with pytest.raises(ValueError,match="Target compilation"):
        validate_evidence(g,f)
    g,f=fake_receipts(tmp_path/"next")
    file=g/"LID_RETENTION_GEOMETRY_EVIDENCE.json"
    body=json.loads(file.read_text())
    body["assembly_authorized"]=True
    put(g,"LID_RETENTION_GEOMETRY_EVIDENCE.json",body)
    with pytest.raises(ValueError,match="promoted"):
        validate_evidence(g,f)
