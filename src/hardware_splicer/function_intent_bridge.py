"""Function-first intent → existing HS MachineProject (concept authority only).

This bridge reuses MachineProject rather than creating an independent machine
registry or an optimistic, manually assigned 'verified' state. It translates
explicit requirements, their tests, functions, allocated disciplines and
interfaces. No sensor, filter, CAD, firmware or physical test is executed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .machine_project import (
    AuthorityState, Domain, Function, Interface, InterfaceContract,
    InterfaceEndpoint, LifecycleState, MachineProject, ReleaseState,
    Requirement, RequirementKind, Subsystem, VerificationMethod,
    VerificationStatus, VerificationType,
)

SCHEMA = "hardware_splicer.function_intent.v1"
GATE_SCHEMA = "hardware_splicer.function_intent_gate.v1"
ALLOWED_USE_CASES = {"non_potable_bench", "general_device", "industrial_research"}
HAZARDOUS_CLAIM_TOKENS = {"potable", "drinkable", "safe_to_drink", "certified", "sterile"}


def canonical(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(dict(value), indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError("Functionality contract refused: " + reason)


def unique(rows: list[dict], key: str) -> set[str]:
    ids = [row.get(key) for row in rows]
    require(bool(ids) and all(isinstance(x, str) and x.strip() for x in ids),
            f"missing {key}")
    require(len(set(ids)) == len(ids), f"duplicate {key}")
    return set(ids)


def parse_intent(intent: Mapping[str, Any]) -> tuple[MachineProject, dict[str, Any]]:
    require(intent.get("schema_version") == SCHEMA, "unknown intent schema")
    require(intent.get("intended_use") in ALLOWED_USE_CASES, "unqualified intended use")
    for forbidden in ("physical_authority_granted", "fabrication_authorized", "potable_certified"):
        require(intent.get(forbidden) is not True, "unsupported safety authority field " + forbidden)
    for value in intent.get("claims", []):
        require(isinstance(value, str) and value.lower().strip() not in HAZARDOUS_CLAIM_TOKENS,
                "unverified health/safety or certification claim")
    id_ = intent.get("project_id")
    purpose = intent.get("purpose")
    require(isinstance(id_, str) and id_.strip() and isinstance(purpose, str) and purpose.strip(),
            "project needs an identity and purpose")
    inputs = intent.get("inputs")
    outputs = intent.get("outputs")
    require(isinstance(inputs, list) and inputs and isinstance(outputs, list) and outputs,
            "explicit input and output streams must be declared")
    for port in inputs + outputs:
        require(isinstance(port, dict) and isinstance(port.get("id"), str)
                and isinstance(port.get("medium"), str) and port["medium"].strip(),
                "streams require id and physical medium")

    requirements = intent.get("requirements")
    functions = intent.get("functions")
    subsystems = intent.get("subsystems")
    interfaces = intent.get("interfaces")
    require(all(isinstance(rows, list) and all(isinstance(item, dict) for item in rows)
                for rows in (requirements, functions, subsystems, interfaces)),
            "requirements, functions, subsystems and interfaces must be explicit lists")
    req_ids = unique(requirements, "id")
    fun_ids = unique(functions, "id")
    subsystem_ids = unique(subsystems, "id")
    interface_ids = unique(interfaces, "id")
    require(not (req_ids & fun_ids or req_ids & subsystem_ids or fun_ids & subsystem_ids
                 or interface_ids & (req_ids | fun_ids | subsystem_ids)),
            "identifiers across graph entities must not collide")
    projected_requirements = []
    verifications = []
    for row in requirements:
        ver = row.get("verification")
        require(isinstance(ver, dict), "requirement " + row["id"] + " missing independent test")
        vid = "verify-" + row["id"]
        require(isinstance(ver.get("procedure"), str) and ver["procedure"].strip()
                and isinstance(ver.get("acceptance"), dict) and ver["acceptance"],
                "requirement " + row["id"] + " lacks observable acceptance criteria")
        require(ver.get("evidence_status", "not_collected") == "not_collected",
                "unverified functional intent cannot import measured or passed results")
        require(row.get("claimed_pass") is not True and row.get("measured") is not True,
                "declared performance cannot be silently promoted to measured")
        assigned = [sub["id"] for sub in subsystems if row["id"] in sub.get("requirements", [])]
        require(bool(assigned), "requirement " + row["id"] + " has no engineering owner")
        projected_requirements.append(Requirement(
            requirement_id=row["id"], statement=row["statement"],
            kind=RequirementKind(row["kind"]), priority=row.get("priority", "must"),
            source="user_functional_spec", allocated_to=assigned,
            verification_method_ids=[vid], authority=AuthorityState.DECLARED,
            metadata={"target": row.get("target"), "acceptance_not_observed": True},
        ))
        verifications.append(VerificationMethod(
            verification_id=vid, name=ver.get("name", vid),
            method_type=VerificationType(ver.get("method_type", "test")),
            status=VerificationStatus.PLANNED, requirement_ids=[row["id"]],
            target_ids=assigned, evidence_ids=[],
            procedure=ver["procedure"], acceptance_criteria=ver["acceptance"],
            authority=AuthorityState.PROPOSED,
        ))

    produced_functions = []
    for fn in functions:
        refs = fn.get("requirements", [])
        owners = fn.get("subsystems", [])
        require(isinstance(refs, list) and bool(refs) and set(refs) <= req_ids,
                "function " + fn["id"] + " has missing or invalid requirements")
        require(isinstance(owners, list) and bool(owners) and set(owners) <= subsystem_ids,
                "function " + fn["id"] + " has no valid engineering allocation")
        produced_functions.append(Function(
            function_id=fn["id"], name=fn["name"], description=fn.get("description",""),
            requirement_ids=refs, allocated_subsystem_ids=owners,
            authority=AuthorityState.PROPOSED,
            metadata={"physical_principle": fn.get("physical_principle","not_selected"),
                      "candidate_technology": fn.get("candidate_technology","unselected")},
        ))
    covered = {id for fn in functions for id in fn["requirements"]}
    require(req_ids <= covered, "every requirement must trace into at least one physical function")

    produced_subsystems = []
    for sub in subsystems:
        refs=sub.get("requirements", [])
        require(set(refs) <= req_ids, "subsystem has unknown requirement")
        produced_subsystems.append(Subsystem(
            subsystem_id=sub["id"], name=sub["name"], domain=Domain(sub["domain"]),
            purpose=sub["purpose"], requirement_ids=refs,
            function_ids=[fn["id"] for fn in functions if sub["id"] in fn.get("subsystems",[])],
            interface_ids=[iface["id"] for iface in interfaces
                           if sub["id"] in (iface.get("from"),iface.get("to"))],
            authority=AuthorityState.PROPOSED,
            metadata={"engineering_specialty":sub.get("engineering_specialty",sub["domain"]),
                      "design_artifact_state":"not_generated"},
        ))

    produced_interfaces = []
    for wire in interfaces:
        left,right=wire.get("from"),wire.get("to")
        require(left in subsystem_ids and right in subsystem_ids and left!=right,
                "interface endpoint must reference two distinct subsystems")
        require(isinstance(wire.get("medium"),str) and wire["medium"].strip(),
                "interface requires its physical medium")
        unresolved=wire.get("unresolved", [])
        require(isinstance(unresolved,list) and unresolved
                and all(isinstance(x,str) and x.strip() for x in unresolved),
                "unverified interface must document unresolved parameters")
        produced_interfaces.append(Interface(
            interface_id=wire["id"], name=wire["name"], kind=wire["medium"],
            endpoints=[InterfaceEndpoint(object_id=left,port=wire.get("from_port","out")),
                       InterfaceEndpoint(object_id=right,port=wire.get("to_port","in"))],
            contracts=[InterfaceContract(
                contract_type=wire["medium"],
                values={"intent":wire.get("intent", ""),
                        "direction":f"{left}->{right}"},
                unresolved_fields=unresolved,
                authority=AuthorityState.PROPOSED)],
            requirement_ids=[r for r in wire.get("requirements", []) if r in req_ids],
            authority=AuthorityState.PROPOSED,
        ))
        require(set(wire.get("requirements",[])) <= req_ids,
                "interface references unknown requirement")

    model = MachineProject(
        project_id=id_, name=intent.get("name",id_), purpose=purpose,
        lifecycle_state=LifecycleState.INTAKE, requested_release_state=ReleaseState.CONCEPT,
        requirements=projected_requirements, functions=produced_functions,
        subsystems=produced_subsystems, interfaces=produced_interfaces,
        verifications=verifications,
        discipline_payloads={"functional_intent":{
            "input_streams":inputs,"output_streams":outputs,
            "use_case":intent["intended_use"],
            "design_status":"FUNCTIONAL_CONCEPT_ONLY",
        }},
        metadata={"source_spec_sha256":hashlib.sha256(canonical(intent)).hexdigest(),
                  "importer":"function_intent_to_machine_project"},
    )
    issues=model.traceability_issues()
    require(not any(i.severity=="error" for i in issues),
            "existing MachineProject identified bad graph references")
    authority={
        "design_ready":False, "build_ready":False,
        "fabrication":False,"firmware_flash":False,
        "power_on":False,"operation":False,
        "treatment_performance_verified":False,
        "water_safe_to_drink":False,
    }
    report={
        "schema_version":GATE_SCHEMA,
        "source_spec_sha256":model.metadata["source_spec_sha256"],
        "project_id":id_,
        "functional_traceability_pass":True,
        "requirements_count":len(requirements),
        "functions_count":len(functions),
        "subsystem_disciplines":{s.subsystem_id:s.metadata["engineering_specialty"]
                                 for s in model.subsystems},
        "interface_count":len(interfaces),
        "planned_independent_tests":len(verifications),
        "evidence_collected_count":0,
        "status":"FUNCTIONAL_CONCEPT_ONLY",
        "machine_project_release_request":"concept",
        "physical_authority":authority,
        "open_engineering_gates":[
            "Select evidence-backed process/technology alternatives",
            "Determine inlet quality and exact intended output",
            "Verify hydraulic/process model with measured properties and media",
            "Choose qualified wetted materials, seals and rated connectors",
            "Generate and independently validate domain-native engineering artifacts",
            "Collect physical function, leakage, durability and treatment evidence",
            "Require independent health/safety qualification before any human exposure",
        ],
    }
    return model,report


def package_intent(source: Mapping[str,Any],out:Path)->dict:
    model,gate=parse_intent(source)
    out=Path(out)
    require(not out.exists() or (out.is_dir() and not any(out.iterdir())),
            "refusing to overwrite existing engineering package")
    out.mkdir(parents=True,exist_ok=True)
    outputs={
      "FUNCTIONAL_INPUT.json":canonical(source),
      "MACHINE_PROJECT.json":canonical(model.model_dump(mode="json")),
      "FUNCTIONAL_GATE.json":canonical(gate),
    }
    for name,payload in outputs.items():
        (out/name).write_bytes(payload)
    receipt={
        "schema_version":"hardware_splicer.function_intent_receipt.v1",
        "source_spec_sha256":gate["source_spec_sha256"],
        "files":{name:{"sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data)}
                 for name,data in sorted(outputs.items())},
        "manufacturing_authorized":False,
        "operation_authorized":False,
    }
    (out/"PACKAGE_RECEIPT.json").write_bytes(canonical(receipt))
    return receipt
