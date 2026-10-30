"""Fail-closed cross-job acceptance evidence for ESP32 Sensor 001.

Two *independently executed* CI toolchains publish actual files. This module
checks those files, not reported success strings or hosted workflow status.
The result is an evidence contract that Atlas can consume without a runtime
dependency on Hardware Splicer.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA="hardware_splicer.engineering_acceptance.v1"
ATLAS_SCHEMA="hardware_splicer.external_capability.v1"


def digest(content:bytes)->str:
    return hashlib.sha256(content).hexdigest()


def read_json(root:Path,name:str)->dict:
    value=json.loads((root/name).read_text())
    if not isinstance(value,dict):
        raise ValueError("Expected JSON object: "+name)
    return value


def check(flag:bool,description:str)->None:
    if not flag:
        raise ValueError("FAIL CLOSED: "+description)


def verified_file(root:Path,name:str,expected:dict)->dict:
    path=root/name
    check(path.is_file(),f"Missing artifact {name}")
    raw=path.read_bytes()
    check(len(raw)>0,f"Empty artifact {name}")
    check(len(raw)==expected.get("bytes"),f"Size mismatch {name}")
    check(digest(raw)==expected.get("sha256"),f"SHA256 mismatch {name}")
    return {"path":name,"sha256":digest(raw),"bytes":len(raw),"verified":True}


def validate_evidence(geometry_dir:Path,firmware_dir:Path)->tuple[dict,dict]:
    """Validate real native tool outputs and compose portable capability data."""
    geometry_dir=Path(geometry_dir)
    firmware_dir=Path(firmware_dir)
    g_receipt=read_json(geometry_dir,"CROSS_DOMAIN_RECEIPT.json")
    f_receipt=read_json(firmware_dir,"CROSS_DOMAIN_RECEIPT.json")
    check(g_receipt==f_receipt,"Independent jobs used different source receipts")
    check(g_receipt.get("schema_version")=="hardware_splicer.cross_domain_sensor_001.v1","Unknown receipt schema")
    check(g_receipt.get("revision_consistent") is True,"Revision consistency not established")
    for key in ("fabrication_authorized","flashing_authorized","power_on_authorized","device_physically_assembled","hardware_measurements_present"):
        check(g_receipt.get(key) is False,f"Unexpected physical authority: {key}")

    artifacts={}
    bound=g_receipt["artifacts"]
    for name in ("DEVICE_SPEC.json","DEVICE_PLAN.json","FIRMWARE_SOURCE.zip",
                 "ENCLOSURE_INPUT.json","VENTILATION_PLAN.json","enclosure.scad"):
        artifacts[name]=verified_file(geometry_dir,name,bound[name])
    check(artifacts["DEVICE_SPEC.json"]["sha256"]==g_receipt.get("source_spec_sha256"),"Spec digest invalid")
    source_spec=read_json(geometry_dir,"DEVICE_SPEC.json")
    device_plan=read_json(geometry_dir,"DEVICE_PLAN.json")
    check(isinstance(source_spec.get("modules"),list) and isinstance(device_plan.get("modules"),list),
          "Invalid device specification or plan")
    check(artifacts["FIRMWARE_SOURCE.zip"]["sha256"]==f_receipt["artifacts"]["FIRMWARE_SOURCE.zip"]["sha256"],
          "Firmware zip and geometry revision differ")

    geom=read_json(geometry_dir,"GEOMETRY_EVIDENCE.json")
    check(geom.get("schema_version")=="hardware_splicer.cross_domain_geometry_evidence.v1","Unrecognized native CAD evidence")
    check(geom.get("source_spec_sha256")==g_receipt["source_spec_sha256"],"Native geometry source revision changed")
    check(geom.get("checked_source_artifact_hashes") is True,"CAD source had no provenance verification")
    check(geom.get("usb_opening",{}).get("observed_3d_subtraction") is True,"No measured mesh USB opening")
    check(geom.get("ventilation_openings",{}).get("vent_cuts_independently_verified") is True,"No measured mesh vents")
    check(geom.get("ventilation_openings",{}).get("ambient_airflow_performance_verified") is False,"Unreviewed real airflow claim")
    check(geom.get("physical_fit_verified") is False and geom.get("manufacturing_authorized") is False,
          "Geometry improperly promoted to physical")
    for key,filename in (("base","enclosure_base.stl"),("lid","enclosure_lid.stl")):
        row=geom[key]
        check(row.get("watertight") is True and row.get("consistent_winding") is True,"Mesh invalid: "+filename)
        artifacts[filename]=verified_file(geometry_dir,filename,row)

    retain=read_json(geometry_dir,"LID_RETENTION_GEOMETRY_EVIDENCE.json")
    plan=read_json(geometry_dir,"LID_RETENTION_PLAN.json")
    check(retain.get("schema_version")=="hardware_splicer.lid_retention_mesh_evidence.v1",
          "Unknown mechanical retention proof")
    check(retain.get("source_spec_sha256")==g_receipt["source_spec_sha256"],
          "Fastening geometry bound to a different source")
    artifacts["LID_RETENTION_PLAN.json"]={
        "path":"LID_RETENTION_PLAN.json",
        "sha256":digest((geometry_dir/"LID_RETENTION_PLAN.json").read_bytes()),
        "verified":True,
    }
    check(retain.get("lid_retention_plan_sha256")==artifacts["LID_RETENTION_PLAN.json"]["sha256"],
          "Retention plan was altered after native render")
    check(retain.get("geometry_source_sha256")==digest((geometry_dir/"enclosure_retained.scad").read_bytes()),
          "Retention CAD source mismatch")
    check(retain.get("retention_ear_and_hole_geometry_verified") is True,"Physical CAD tabs not checked")
    check(plan.get("board_mounting",{}).get("status")=="BLOCKED_UNVERIFIED_BOARD_MOUNT_HOLES",
          "PCB mounting falsely qualified")
    for key in ("board_mounting_verified","physical_fit_verified","assembly_authorized","manufacturing_authorized"):
        check(retain.get(key) is False,"Retention falsely promoted "+key)
    for key,filename in (("retained_base","retained_base.stl"),("retained_lid","retained_lid.stl")):
        row=retain[key]
        check(row.get("watertight") is True and row.get("consistent_winding") is True,
              "Invalid fastening mesh: "+filename)
        artifacts[filename]=verified_file(geometry_dir,filename,row)

    compiled=read_json(firmware_dir,"FIRMWARE_TARGET_COMPILE_EVIDENCE.json")
    check(compiled.get("schema_version")=="hardware_splicer.cross_domain_target_compile.v1",
          "Unknown embedded compile schema")
    check(compiled.get("source_spec_sha256")==g_receipt["source_spec_sha256"],
          "Embedded compile used stale design specification")
    check(compiled.get("firmware_source_zip_sha256")==artifacts["FIRMWARE_SOURCE.zip"]["sha256"],
          "Compiled application source zip not tied to CAD")
    check(compiled.get("compile_pass") is True and compiled.get("exit_code")==0,
          "Target compilation failed or not executed")
    check(compiled.get("toolchain")=="PlatformIO Core, version 6.1.18",
          "Unexpected embedded compiler version")
    check(compiled.get("command")==["pio","run","--environment","application","--jobs","2"],
          "Unexpected target build invocation")
    for key in ("real_hardware_flashing","physical_behavior_verified","firmware_authorized","power_on_authorized"):
        check(compiled.get(key) is False,"Firmware promoted to hardware authority "+key)
    artifacts["PLATFORMIO_COMPILE.log"]={
        "path":"PLATFORMIO_COMPILE.log",
        "sha256":digest((firmware_dir/"PLATFORMIO_COMPILE.log").read_bytes()),
        "verified":True,
    }
    check(artifacts["PLATFORMIO_COMPILE.log"]["sha256"]==compiled.get("compile_log_sha256"),
          "Compiler log was modified")
    for binary in ("firmware.elf","firmware.bin"):
        actual_path=firmware_dir/"platformio-application/.pio/build/application"/binary
        artifacts[binary]=verified_file(firmware_dir,str(actual_path.relative_to(firmware_dir)),
                                         compiled["compiled_artifacts"][binary])
    check(set(compiled.get("compiled_artifacts",{}))=={"firmware.bin","firmware.elf"},
          "Unexpected or missing native target artifacts")

    # Symbolic catalog/firmware source preflight is separate from native KiCad.
    electrical=read_json(geometry_dir,"ELECTRICAL_PREFLIGHT.json")
    bom=read_json(geometry_dir,"BOM_PROVENANCE.json")
    check(electrical.get("schema_version")=="hardware_splicer.sensor_electrical_preflight.v1",
          "Missing true electrical preflight schema")
    check(bom.get("schema_version")=="hardware_splicer.sensor_bom_provenance.v1",
          "Missing procurement traceability schema")
    for record in (electrical,bom):
        check(record.get("source_spec_sha256")==g_receipt["source_spec_sha256"],
              "Electrical/BOM revision does not match compiled firmware and geometry")
    check(electrical.get("firmware_source_zip_sha256")==artifacts["FIRMWARE_SOURCE.zip"]["sha256"],
          "Electrical audit is not bound to the compiled firmware source")
    check(electrical.get("software_source_pin_consistency") is True
          and electrical.get("symbolic_catalog_net_consistency") is True,
          "Symbolic electrical or source GPIO validation missing")
    check(electrical.get("i2c_gpios")=={"sda":21,"scl":22},
          "Unexpected tested ESP32 reference I2C pin contract")
    check(electrical.get("native_kicad_erc_drc_executed") is False
          and electrical.get("electrical_hardware_qualified") is False
          and electrical.get("power_on_authorized") is False
          and electrical.get("fabrication_authorized") is False,
          "Electrical preflight falsely claims physical or native EDA authority")
    check(len(bom.get("parts",[]))==2
          and {p.get("catalog_id") for p in bom["parts"]}=={
              "esp32-devkitc-v4","adafruit-bme280-stemma-qt"},
          "BOM missing or identifying wrong catalog modules")
    check(all(p.get("sources") and p.get("procurement_status")=="UNQUALIFIED"
              and p.get("electrical_ratings_verified_on_real_board") is False
              for p in bom["parts"]), "BOM falsely qualifies unknown vendor parts")
    check(bom.get("bom_fabrication_ready") is False
          and bom.get("supplier_price_verified") is False
          and bom.get("supply_current_budget_measured") is False,
          "BOM falsely claims procurement or electrical measurement authority")
    for name in ("ELECTRICAL_PREFLIGHT.json","BOM_PROVENANCE.json"):
        body=(geometry_dir/name).read_bytes()
        artifacts[name]={"path":name,"sha256":digest(body),"bytes":len(body),"verified":True}

    report={
      "schema_version":SCHEMA,
      "capability_id":"hs.esp32_sensor_001.cross_domain_software",
      "source_spec_sha256":g_receipt["source_spec_sha256"],
      "verified_native_toolchains":["OpenSCAD + trimesh","PlatformIO Core 6.1.18 / Espressif32 6.10.0"],
      "verified_domains":{
          "electrical":"catalog_wiring_and_firmware_pin_preflight_only",
          "firmware":"actual_esp32_target_cross_compile",
          "mechanical":"native_openscad_watertight_measured_meshes",
          "physical":"not_measured",
          "manufacturing":"not_executed",
          "component_sourcing":"catalog_traced_unqualified",
      },
      "cross_domain_consistency_pass":True,
      "artifact_hashes_verified":artifacts,
      "release_readiness":"software_candidate_only",
      "unresolved_blockers":[
          "no_native_custom_kicad_board_or_verified_electrical_drc",
          "no_qualified_manufacturer_orderable_revisions_or_verified_pricing",
          "unverified_i2c_pullups_and_actual_supply_current",
          "no_actual_bme280_sensor_or_esp32_hardware_measurements",
          "no_measured_board_mounting_holes_or_assembly_fit",
          "no_firmware_flashing_or_real_sensor_behavior",
          "no_bench_thermal_or_mechanical_strength_data",
          "no_fabrication_or_print_profile_verification",
      ],
      "physical_authority":{"fabrication":False,"flashing":False,"power_on":False,"physical_product":False},
    }
    atlas={
      "schema_version":ATLAS_SCHEMA,
      "capability_id":report["capability_id"],
      "provenance":{"source_spec_sha256":report["source_spec_sha256"],
                    "report_sha256":digest((json.dumps(report,indent=2,sort_keys=True)+"\n").encode())},
      "supported_domains":report["verified_domains"],
      "entry_points":[
          "scripts/generate_cross_domain_sensor_001.py",
          "scripts/verify_cross_domain_geometry_001.py",
          "scripts/verify_sensor_retention_001.py",
          "scripts/verify_cross_domain_firmware_target_001.py",
          "scripts/verify_sensor_electrical_preflight_001.py",
      ],
      "input_requirements":{
          "source_format":"JSON with module identities and I2C pin bindings",
          "supported_device_case":"ESP32 DevKitC V4 + BME280 catalog wiring and enclosure",
          "source_spec_sha256":report["source_spec_sha256"],
          "qualified_physical_parts_required_for_build":True,
      },
      "artifact_types":[
          "device_wiring_plan_json","firmware_source_zip","esp32_elf","esp32_bin",
          "openscad_source","stl_mesh","geometry_evidence_json","sha256_receipt",
          "symbolic_electrical_preflight_json","unqualified_bom_provenance_json",
      ],
      "reproduction_commands":[
          "python scripts/generate_cross_domain_sensor_001.py --output /tmp/hs-sensor-001",
          "python scripts/verify_cross_domain_geometry_001.py --project /tmp/hs-sensor-001",
          "python scripts/generate_sensor_retention_001.py --project /tmp/hs-sensor-001",
          "python scripts/verify_sensor_retention_001.py --project /tmp/hs-sensor-001",
          "python scripts/verify_cross_domain_firmware_target_001.py --project /tmp/hs-sensor-001",
          "python scripts/verify_cross_domain_acceptance_001.py --geometry <ci-geometry-artifact> --firmware <ci-firmware-artifact> --out <fresh-output>",
      ],
      "external_dependencies":{
          "embedded":"PlatformIO Core 6.1.18 and Espressif32 6.10.0",
          "mechanical":"OpenSCAD CLI and trimesh (CI pinned to 4.8.3)",
          "tested_runtime":"Python 3.12",
      },
      "candidate_use_cases":["ESP32 sensor device development","software-only firmware and mechanical fit preflight"],
      "human_authorization_requirements":[
          "qualified parts, real wiring and bench measurements",
          "supervised firmware flashing and device power-on approval",
          "print material/process profile and physical fit verification",
      ],
      "verification":{"cross_domain_consistency_pass":True,
                      "native_toolchains":report["verified_native_toolchains"],
                      "artifact_count":len(artifacts)},
      "known_limitations":report["unresolved_blockers"],
      "authorization":{"real_world_actuation":False,"fabrication":False},
      "atlas_runtime_required":False,
    }
    return report,atlas


def produce(geometry_dir:Path,firmware_dir:Path,output_dir:Path)->None:
    report,atlas=validate_evidence(geometry_dir,firmware_dir)
    out=Path(output_dir)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError("Refusing to overwrite prior acceptance evidence")
    out.mkdir(parents=True,exist_ok=True)
    (out/"ENGINEERING_ACCEPTANCE.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    (out/"ATLAS_CAPABILITY.json").write_text(json.dumps(atlas,indent=2,sort_keys=True)+"\n")
