"""Illustrative, declared CAD+ERC+real TDS integration benchmark.

Material evidence is tied to the two real Prusa vendor PDFs.
CAD envelopes, mounting locations, clearance dimensions and electrical net are
deliberately synthetic: this is a regression demonstration, not an actual design.
"""
from __future__ import annotations

import copy
import json

from fastapi.testclient import TestClient
from hardware_splicer.product_api import create_product_app
from hardware_splicer.step_geometry import parse_step_model, build_mechanical_geometry_report
try:
    from .prusa_enclosure_screen_v1 import make_project
except ImportError:  # direct invocation as a script
    from prusa_enclosure_screen_v1 import make_project

STEP = """ISO-10303-21;
HEADER;
FILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));
ENDSEC;
DATA;
#1=PRODUCT('enclosure-reference','Reference','',());
#2=SI_UNIT(.MILLI.,.METRE.);
#3=CARTESIAN_POINT('',(0.0,0.0,0.0));
#4=CARTESIAN_POINT('',({x}.0,{y}.0,{z}.0));
ENDSEC;
END-ISO-10303-21;
"""


def request_body(selected: str = "candidate-pc_blend", *,
                 source_evidence: list[dict] | None = None) -> dict:
    project = make_project()
    if source_evidence is not None:
        project["evidence"] = copy.deepcopy(source_evidence)
    project["subsystems"].append({
        "subsystem_id": "electronics",
        "name": "Electrical subsystem",
        "domain": "electrical",
    })
    project["components"].extend([
        {"component_id": "pcb", "name": "PCB and controller", "domain": "electrical",
         "subsystem_id": "electronics"},
        {"component_id": "load", "name": "Sensor load", "domain": "electrical",
         "subsystem_id": "electronics"},
    ])
    mechanical_models = [
        parse_step_model(STEP.format(x=120, y=75, z=30),
                         source_id="declared:enclosure-shell", model_id="shell-cad"),
        parse_step_model(STEP.format(x=100, y=55, z=10),
                         source_id="declared:board-reference", model_id="board-cad"),
    ]
    pattern = {"count": 4, "spacing_x_mm": 40.0,
               "spacing_y_mm": 25.0, "hole_diameter_mm": 3.2}
    mounts = [
        {"interface_id": "enclosure-bosses", "part_id": selected,
         "cad_model_id": "shell-cad", "mount_type": "flat_flange",
         "mates_with": "board-mounts", "datum_frame": "assembly",
         "origin_mm": [15, 15, 5], "normal": [0, 0, 1],
         "fastener_spec": "M3", "hole_pattern": pattern},
        {"interface_id": "board-mounts", "part_id": "pcb",
         "cad_model_id": "board-cad", "mount_type": "flat_flange",
         "mates_with": "enclosure-bosses", "datum_frame": "assembly",
         "origin_mm": [15, 15, 5], "normal": [0, 0, -1],
         "fastener_spec": "M3", "hole_pattern": pattern},
    ]
    geometry = build_mechanical_geometry_report(
        project_id=project["project_id"], models=mechanical_models,
        mounts=mounts,
    )
    electrical_design = {
        "design_id": "enclosure-electronics-review",
        "project_id": project["project_id"],
        "components": [
            {"component_id": "pcb", "reference": "U1",
             "name": "Control board", "pin_ids": ["pcb-out"]},
            {"component_id": "load", "reference": "J1",
             "name": "Sensor load", "pin_ids": ["load-in"]},
        ],
        "pins": [
            {"pin_id": "pcb-out", "component_id": "pcb", "name": "OUT",
             "number": "1", "electrical_type": "output", "net_id": "sense"},
            {"pin_id": "load-in", "component_id": "load", "name": "IN",
             "number": "1", "electrical_type": "input", "net_id": "sense", "required": True},
        ],
        "nets": [{"net_id": "sense", "name": "SENSE", "kind": "signal",
                  "pin_ids": ["pcb-out", "load-in"]}],
    }
    return {
        "project": project,
        "candidate_ids": ["candidate-asa", "candidate-pc_blend"],
        "selected_enclosure_id": selected,
        "electrical_component_id": "pcb",
        "electrical_design": electrical_design,
        "mechanical_geometry": geometry.model_dump(mode="json"),
        "clearance_boxes": [
            {"object_id": selected, "frame_id": "assembly",
             "minimum_mm": [0, 0, 14], "maximum_mm": [120, 75, 17],
             "metadata": {"meaning": "declared_lid_exclusion_volume_not_full_shell"}},
            {"object_id": "pcb", "frame_id": "assembly",
             "minimum_mm": [15, 15, 4], "maximum_mm": [100, 55, 6],
             "metadata": {"meaning": "declared_board_occupied_envelope"}},
        ],
        "clearance_requirements": [
            {"requirement_id": "lid-pcb-z-clearance",
             "first_object_id": selected,
             "second_object_id": "pcb",
             "minimum_clearance_mm": 5.0}
        ],
    }


def scenarios() -> list[dict]:
    base = request_body()
    asa = request_body("candidate-asa")
    collision = copy.deepcopy(base)
    collision["clearance_boxes"][0]["minimum_mm"] = [0, 0, 5]
    collision["clearance_boxes"][0]["maximum_mm"] = [120, 75, 7]
    bad_erc = copy.deepcopy(base)
    bad_erc["electrical_design"]["pins"][1]["electrical_type"] = "output"
    missing_clearance = copy.deepcopy(base)
    missing_clearance["clearance_requirements"][0]["second_object_id"] = "load"
    wrong_model_id = copy.deepcopy(base)
    wrong_model_id["mechanical_geometry"]["project_id"] = "another-machine"
    disconnected_mount = copy.deepcopy(base)
    disconnected_mount["mechanical_geometry"]["mounts"][0]["part_id"] = "candidate-asa"
    disconnected_mount["mechanical_geometry"]["mounts"][1]["part_id"] = "pcb"
    unmapped_electrical = copy.deepcopy(base)
    unmapped_electrical["electrical_design"]["components"][1]["component_id"] = "external-load"
    unmapped_electrical["electrical_design"]["pins"][1]["component_id"] = "external-load"
    forged_fit = copy.deepcopy(collision)
    forged_fit["mechanical_geometry"]["checks"] = []
    forged_fit["mechanical_geometry"]["status"] = "candidate"
    missing_hdt = copy.deepcopy(base)
    missing_hdt["project"]["evidence"] = [
        e for e in missing_hdt["project"]["evidence"]
        if e["evidence_id"] != "prusa-tds-pc_blend-0p45"
    ]
    unequal_material = copy.deepcopy(base)
    unequal_material["project"]["constraints"] = [
        c for c in unequal_material["project"]["constraints"]
        if c["constraint_id"] != "hdt-1p8-pc_blend"
    ]
    unequal_material["project"]["evidence"] = [
        e for e in unequal_material["project"]["evidence"]
        if e["evidence_id"] != "prusa-tds-pc_blend-1p8"
    ]
    return [
        {"id": "declared_candidate_screen", "body": base, "expected": "bounded_assembly_screen_consistent_but_unverified"},
        {"id": "asa_hdt_fails", "body": asa, "expected": "assembly_screen_blocked"},
        {"id": "actual_declared_collision", "body": collision, "expected": "assembly_screen_blocked"},
        {"id": "electrical_driver_conflict", "body": bad_erc, "expected": "assembly_screen_blocked"},
        {"id": "clearance_coverage_missing", "body": missing_clearance, "expected": "assembly_screen_blocked"},
        {"id": "project_id_mismatch", "body": wrong_model_id, "expected_http": 422},
        {"id": "forged_pass_report", "body": forged_fit, "expected": "assembly_screen_blocked"},
        {"id": "unmapped_electrical_component", "body": unmapped_electrical, "expected": "assembly_screen_blocked"},
        {"id": "disconnected_selected_mount", "body": disconnected_mount, "expected": "assembly_screen_blocked"},
        {"id": "missing_material_evidence", "body": missing_hdt, "expected": "assembly_screen_blocked"},
        {"id": "unequal_material_constraints", "body": unequal_material, "expected": "assembly_screen_blocked"},
    ]


def run():
    app = TestClient(create_product_app())
    rows = []
    for scenario in scenarios():
        response = app.post("/v1/engineering/chemical/enclosure/assembly-review",
                            json=scenario["body"])
        if scenario.get("expected_http"):
            passed = response.status_code == scenario["expected_http"]
            rows.append({"scenario": scenario["id"], "pass": passed,
                         "http_status": response.status_code})
            continue
        if response.status_code != 200:
            rows.append({"scenario": scenario["id"], "pass": False,
                         "http_status": response.status_code, "error": response.text[:650]})
            continue
        body = response.json()
        passed = (body["result"] == scenario["expected"] and
                  not body["build_readiness_authorized"] and
                  not body["fabrication_authorized"] and
                  not body["release_authorized"])
        if scenario["id"] == "forged_pass_report":
            passed = passed and bool(body["mechanical"]["fit_failed_check_ids"])
        rows.append({"scenario": scenario["id"], "pass": passed, "result": body["result"],
                     "finding_codes": [r["code"] for r in body["blocking_findings"]],
                     "geometry_checks": body["mechanical"]["geometry_computed_check_count"],
                     "fit_checks": body["mechanical"]["fit_computed_check_count"],
                     "erc_errors": body["electrical"]["erc_error_count"],
                     "authorized": body["build_readiness_authorized"]})
    return {"schema_version": "hardware_splicer.three_layer_enclosure_benchmark.v1",
            "scenario_count": len(rows),
            "passing_count": sum(x["pass"] for x in rows),
            "scenarios": rows,
            "limitations": [
                "Material values come from real pinned Prusa PDFs but their source authentication is not rerun in this benchmark.",
                "Geometry, clearance and electrical net are synthetic declared engineering objects.",
                "Computed agreement is an analytical screen, not real hardware validation or safe design approval.",
            ]}


if __name__ == "__main__":
    report = run()
    print(json.dumps(report, indent=2))
    if report["passing_count"] != report["scenario_count"]:
        raise SystemExit(1)
