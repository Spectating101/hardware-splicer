"""Reconcile the existing ESP32 native engineering proof into HS's MachineProject.

This is a SECOND product family next to ClearBench, not an ESP32->filter adapter.
Native evidence is independently revalidated before building the machine record.
Digital CLI/mesh/firmware success never becomes electrical, physical, or release approval.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .engineering_acceptance_sensor import validate_evidence
from .machine_project import (
    ArtifactRef, AuthorityState, Component, ComponentSource, Domain, EvidenceRef,
    Function, Interface, InterfaceContract, InterfaceEndpoint, LifecycleState,
    MachineProject, ReleaseState, Requirement, RequirementKind, Subsystem,
    VerificationMethod, VerificationStatus, VerificationType,
)

SCHEMA = "hardware_splicer.product_handoff.v1"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError("Sensor machine handoff refused: " + message)


def from_verified_sensor(report: dict, atlas: dict, source: dict, wiring: dict,
                         electrical: dict) -> tuple[MachineProject, dict]:
    """Only call after validate_evidence on actual native source files.

    Unit tests can supply synthetic *already validated* reports to check this
    mapping; synthetic tests DO NOT validate any external engineering tool.
    """
    source_sha = report.get("source_spec_sha256")
    require(isinstance(source_sha, str) and len(source_sha) == 64
            and all(c in "0123456789abcdef" for c in source_sha),
            "missing original device specification digest")
    require(report.get("schema_version") == "hardware_splicer.engineering_acceptance.v1"
            and report.get("cross_domain_consistency_pass") is True
            and report.get("release_readiness") == "software_candidate_only",
            "native cross-domain acceptance not established")
    require(atlas.get("schema_version") == "hardware_splicer.external_capability.v1"
            and atlas.get("provenance", {}).get("source_spec_sha256") == source_sha
            and atlas.get("provenance", {}).get("report_sha256") == digest(canonical(report)),
            "Atlas capability does not match validated source and acceptance")
    require(not any(report.get("physical_authority", {}).values())
            and set(report.get("physical_authority", {})) ==
            {"fabrication", "flashing", "power_on", "physical_product"}
            and atlas.get("authorization") ==
            {"real_world_actuation": False, "fabrication": False},
            "physical authorization must remain closed")
    require(electrical.get("source_spec_sha256") == source_sha
            and electrical.get("software_source_pin_consistency") is True
            and electrical.get("symbolic_catalog_net_consistency") is True
            and electrical.get("i2c_gpios") == {"sda": 21, "scl": 22}
            and electrical.get("native_kicad_erc_drc_executed") is False,
            "symbolic net/firmware contract not independently qualified")
    require(isinstance(source.get("modules"), list)
            and isinstance(wiring.get("modules"), list)
            and {m["id"] for m in wiring["modules"]} == {"mcu", "sensor"}
            and {m["module"] for m in wiring["modules"]} ==
            {"esp32-devkitc-v4", "adafruit-bme280-stemma-qt"},
            "wrong electronic product or device plan")
    proof = report.get("artifact_hashes_verified", {})
    required = {
        "DEVICE_SPEC.json", "ELECTRICAL_PREFLIGHT.json", "firmware.bin",
        "firmware.elf", "enclosure_base.stl", "enclosure_lid.stl",
        "retained_base.stl", "retained_lid.stl",
    }
    require(required <= set(proof) and all(
        proof[k].get("verified") is True
        and isinstance(proof[k].get("sha256"), str)
        and len(proof[k]["sha256"]) == 64 for k in required
    ), "missing native binary, CAD or preflight evidence")
    require(proof["DEVICE_SPEC.json"]["sha256"] == source_sha,
            "source specification not the accepted native design revision")

    # Requirements distinguish digital gates already passed from physical tests
    # that have never been run. No real-world requirement is marked passed.
    definitions = [
        ("REQ_PINS", "Sourced symbolic I2C netlist matches generated firmware pins",
         RequirementKind.INTERFACE, ["SUB_ELECTRICAL", "SUB_FIRMWARE"],
         "VER_PINS", VerificationStatus.PASSED, ["EV_PINS"]),
        ("REQ_FIRMWARE", "Generate a source-matched ESP32 target binary",
         RequirementKind.FUNCTIONAL, ["SUB_FIRMWARE"],
         "VER_FIRMWARE", VerificationStatus.PASSED, ["EV_BINARY"]),
        ("REQ_CAD", "Generate source-matched, watertight enclosure geometry",
         RequirementKind.FUNCTIONAL, ["SUB_MECHANICAL"],
         "VER_CAD", VerificationStatus.PASSED, ["EV_MESH"]),
        ("REQ_HARDWARE", "Verify actual board fit, mounting, wiring and power safety",
         RequirementKind.SAFETY, ["SUB_ELECTRICAL", "SUB_MECHANICAL"],
         "VER_HARDWARE", VerificationStatus.PLANNED, []),
        ("REQ_OPERATION", "Measure temperature/humidity behavior on an assembled device",
         RequirementKind.PERFORMANCE, ["SUB_ELECTRICAL", "SUB_FIRMWARE"],
         "VER_OPERATION", VerificationStatus.PLANNED, []),
    ]
    requirements = [
        Requirement(requirement_id=rid, statement=label, kind=kind, priority="must",
                    allocated_to=owners, verification_method_ids=[vid],
                    authority=AuthorityState.DECLARED)
        for rid, label, kind, owners, vid, _, _ in definitions
    ]
    checks = [
        VerificationMethod(
            verification_id=vid, name=label, method_type=VerificationType.TEST,
            requirement_ids=[rid], target_ids=owners, status=status,
            evidence_ids=evid, procedure=(
                "Recompute native artifacts and their source-bound hashes"
                if status == VerificationStatus.PASSED
                else "Supervised physical test with independently retained measurements"
            ), acceptance_criteria={"required": True},
            authority=(AuthorityState.VERIFIED if evid else AuthorityState.PROPOSED),
        )
        for rid, label, _, owners, vid, status, evid in definitions
    ]
    evidence = [
        EvidenceRef(evidence_id="EV_PINS", kind="symbolic_electrical_source_audit",
                    basis="source-bound non-physical preflight",
                    ref="sha256:" + proof["ELECTRICAL_PREFLIGHT.json"]["sha256"],
                    supports=["VER_PINS", "REQ_PINS"],
                    authority=AuthorityState.VERIFIED, simulated=True,
                    metadata={"nonphysical_digital_only": True}),
        EvidenceRef(evidence_id="EV_BINARY", kind="native_target_compile",
                    basis="PlatformIO target ELF/BIN; no flashed device",
                    ref="sha256:" + proof["firmware.bin"]["sha256"],
                    supports=["VER_FIRMWARE", "REQ_FIRMWARE"],
                    authority=AuthorityState.VERIFIED, simulated=True,
                    metadata={"elf_sha256": proof["firmware.elf"]["sha256"],
                              "nonphysical_digital_only": True}),
        EvidenceRef(evidence_id="EV_MESH", kind="native_enclosure_geometry",
                    basis="OpenSCAD and independent watertightness checks; no fitted enclosure",
                    ref="sha256:" + proof["enclosure_base.stl"]["sha256"],
                    supports=["VER_CAD", "REQ_CAD"],
                    authority=AuthorityState.VERIFIED, simulated=True,
                    metadata={"lid_sha256": proof["enclosure_lid.stl"]["sha256"],
                              "retained_base_sha256": proof["retained_base.stl"]["sha256"],
                              "nonphysical_digital_only": True}),
    ]
    subsystems = [
        Subsystem(subsystem_id="SUB_ELECTRICAL", name="Catalog hardware and I2C",
                  domain=Domain.ELECTRICAL, purpose="Sensor/MCU power and data wiring",
                  requirement_ids=["REQ_PINS", "REQ_HARDWARE", "REQ_OPERATION"],
                  function_ids=["FN_MEASURE"], component_ids=["COMP_MCU", "COMP_SENSOR"],
                  interface_ids=["IF_I2C", "IF_CASE"]),
        Subsystem(subsystem_id="SUB_FIRMWARE", name="Sensor application",
                  domain=Domain.FIRMWARE, purpose="BME280 data acquisition firmware",
                  requirement_ids=["REQ_PINS", "REQ_FIRMWARE", "REQ_OPERATION"],
                  function_ids=["FN_MEASURE", "FN_COMPILE"]),
        Subsystem(subsystem_id="SUB_MECHANICAL", name="Sensor enclosure",
                  domain=Domain.MECHANICAL, purpose="Printed enclosure design proposal",
                  requirement_ids=["REQ_CAD", "REQ_HARDWARE"],
                  function_ids=["FN_ENCLOSE"], component_ids=["COMP_CASE"],
                  interface_ids=["IF_CASE"]),
    ]
    functions = [
        Function(function_id="FN_MEASURE", name="Read I2C environmental sensor",
                 requirement_ids=["REQ_PINS", "REQ_OPERATION"],
                 allocated_subsystem_ids=["SUB_ELECTRICAL", "SUB_FIRMWARE"]),
        Function(function_id="FN_COMPILE", name="Produce target firmware",
                 requirement_ids=["REQ_FIRMWARE"],
                 allocated_subsystem_ids=["SUB_FIRMWARE"]),
        Function(function_id="FN_ENCLOSE", name="Enclose catalog boards",
                 requirement_ids=["REQ_CAD", "REQ_HARDWARE"],
                 allocated_subsystem_ids=["SUB_MECHANICAL"]),
    ]
    components = [
        Component(component_id="COMP_MCU", name="ESP32 DevKitC V4 catalog module",
                  domain=Domain.ELECTRICAL, subsystem_id="SUB_ELECTRICAL",
                  source=ComponentSource.EXTERNAL, authority=AuthorityState.PROPOSED),
        Component(component_id="COMP_SENSOR", name="Adafruit BME280 breakout",
                  domain=Domain.ELECTRICAL, subsystem_id="SUB_ELECTRICAL",
                  source=ComponentSource.EXTERNAL, authority=AuthorityState.PROPOSED),
        Component(component_id="COMP_CASE", name="Unfabricated enclosure geometry",
                  domain=Domain.MECHANICAL, subsystem_id="SUB_MECHANICAL",
                  source=ComponentSource.GENERATED, authority=AuthorityState.PROPOSED),
    ]
    interfaces = [
        Interface(interface_id="IF_I2C", name="ESP32/BME280 symbolic bus",
                  kind="i2c", endpoints=[
                      InterfaceEndpoint(object_id="COMP_MCU", port="IO21/IO22/3V3/GND"),
                      InterfaceEndpoint(object_id="COMP_SENSOR", port="SDI/SCK/Vin/GND"),
                  ], requirement_ids=["REQ_PINS", "REQ_HARDWARE"],
                  contracts=[InterfaceContract(contract_type="i2c",
                      values={"catalog_sda_gpio": electrical["i2c_gpios"]["sda"],
                              "catalog_scl_gpio": electrical["i2c_gpios"]["scl"]},
                      unresolved_fields=["real_board_pinout", "i2c_pullups",
                                         "physical_rail_current"],
                      authority=AuthorityState.PROPOSED)]),
        Interface(interface_id="IF_CASE", name="Catalog boards to enclosure",
                  kind="mechanical", endpoints=[
                      InterfaceEndpoint(object_id="SUB_ELECTRICAL", port="board_envelopes"),
                      InterfaceEndpoint(object_id="SUB_MECHANICAL", port="mounting_locations"),
                  ], requirement_ids=["REQ_HARDWARE", "REQ_CAD"],
                  contracts=[InterfaceContract(contract_type="mounting",
                      unresolved_fields=["measured_board_holes", "physical_fit",
                                         "fastener_strength", "antenna_clearance"],
                      authority=AuthorityState.PROPOSED)]),
    ]
    artifacts = [
        ArtifactRef(artifact_id="ART_SOURCE", kind="source_spec_sha256",
                    ref="sha256:" + source_sha, authority=AuthorityState.DECLARED),
        ArtifactRef(artifact_id="ART_FIRMWARE", kind="esp32_binary_sha256",
                    ref="sha256:" + proof["firmware.bin"]["sha256"],
                    authority=AuthorityState.VERIFIED,
                    metadata={"digital_only": True}),
        ArtifactRef(artifact_id="ART_MECHANICAL", kind="native_mesh_sha256",
                    ref="sha256:" + proof["enclosure_base.stl"]["sha256"],
                    authority=AuthorityState.VERIFIED,
                    metadata={"digital_only": True}),
    ]
    model = MachineProject(
        project_id="esp32_bme280_sensor_001", name=source.get("name", "ESP32 BME280 sensor"),
        purpose="Source-bound electronic environmental sensing station (digital demonstrator)",
        lifecycle_state=LifecycleState.VERIFY,
        requested_release_state=ReleaseState.CONCEPT,
        requirements=requirements, functions=functions, subsystems=subsystems,
        components=components, interfaces=interfaces, verifications=checks,
        evidence=evidence, artifacts=artifacts,
        metadata={"source_spec_sha256": source_sha,
                  "native_acceptance_sha256": digest(canonical(report)),
                  "product_family": "electronic_environmental_monitor",
                  "physical_release_authorized": False},
    )
    assessment = model.assess_release(ReleaseState.OPERATIONALLY_AUTHORIZED)
    require(not assessment.allowed and
            any(i.code == "safety_not_closed" for i in assessment.blockers),
            "physical release barrier not retained")
    summary = {
        "schema_version": SCHEMA,
        "product_id": model.project_id,
        "product_family": "electronic_environmental_monitor",
        "source_spec_sha256": source_sha,
        "native_acceptance_sha256": digest(canonical(report)),
        "verified_digital_requirements": ["REQ_PINS", "REQ_FIRMWARE", "REQ_CAD"],
        "unverified_physical_requirements": ["REQ_HARDWARE", "REQ_OPERATION"],
        "source_bound_native_toolchains": report["verified_native_toolchains"],
        "product_specimen_complete_digitally": False,
        "physical_assembly_complete": False,
        "manufacturing_authorized": False,
        "firmware_flashing_authorized": False,
        "operation_authorized": False,
        "release_blockers": [i.code for i in assessment.blockers],
        "existing_atlas_capability_id": atlas["capability_id"],
    }
    return model, summary


def export(geometry: Path, firmware: Path, output: Path) -> dict:
    # Revalidate every native input rather than trusting a prior JSON "PASS".
    report, atlas = validate_evidence(geometry, firmware)
    geom = Path(geometry)
    source = json.loads((geom / "DEVICE_SPEC.json").read_text())
    wiring = json.loads((geom / "DEVICE_PLAN.json").read_text())
    electrical = json.loads((geom / "ELECTRICAL_PREFLIGHT.json").read_text())
    model, summary = from_verified_sensor(report, atlas, source, wiring, electrical)
    out = Path(output)
    require(not out.exists() or (out.is_dir() and not any(out.iterdir())),
            "refusing to overwrite existing engineering evidence")
    out.mkdir(parents=True, exist_ok=True)
    outputs = {
        "MACHINE_PROJECT.json": canonical(model.model_dump(mode="json")),
        "PRODUCT_HANDOFF.json": canonical(summary),
        "ENGINEERING_ACCEPTANCE.json": canonical(report),
        "ATLAS_CAPABILITY.json": canonical(atlas),
    }
    for name, body in outputs.items():
        (out / name).write_bytes(body)
    receipt = {
        "schema_version": "hardware_splicer.product_handoff_receipt.v1",
        "source_spec_sha256": summary["source_spec_sha256"],
        "files": {name: {"sha256": digest(body), "bytes": len(body)}
                  for name, body in sorted(outputs.items())},
        "physical_authority_granted": False,
    }
    (out / "HANDOFF_RECEIPT.json").write_bytes(canonical(receipt))
    return receipt
