"""Reproducible, source-version-pinned material screening cases.

All values manually transcribed from page 2 of manufacturer TDS PDFs, not
produced by a document parsing model or independently certified. Thresholds
are hypothetical screening requirements, NOT an enclosure design approval.
"""
from __future__ import annotations

import copy
import json
import time
from pathlib import Path

from fastapi.testclient import TestClient
from hardware_splicer.product_api import create_product_app

SOURCES = {
    "asa": {
        "url": "https://storage.googleapis.com/prusa3d-content-prod-14e8-wordpress-prusament-prod/2024/05/bc8551ef-tds_prusament-asa_2024_en.pdf",
        "sha256": "a8e322580ae1683f398c8a0cfe7c9221747f1b6ec99d2a953e3e48161a959aab",
        "material_id": "Prusament ASA",
        "heat_deflection_c": {0.45: 93, 1.8: 86},
    },
    "pc_blend": {
        "url": "https://prusament.com/wp-content/uploads/2022/10/PCBlend_Prusament_TDS_2022_16_EN.pdf",
        "sha256": "25f7aa7b99cc24e5b7d75fbbfd5fa949a3e5689b7201c6b34a9cb588d7c040c7",
        "material_id": "Prusament PC Blend",
        "heat_deflection_c": {0.45: 113, 1.8: 93},
    },
}


def make_project(*, stress_criteria: list[tuple[float, float]] | None = None,
                 include_electrical: bool = False) -> dict:
    # Celsius thresholds are converted to K so comparisons are strictly unit-aligned.
    criteria = stress_criteria or [(0.45, 100), (1.8, 90)]
    project = {
        "project_id": "prusa-electronics-enclosure-material-screen-v1",
        "name": "FDM electronics enclosure candidate review",
        "purpose": "Evidence-first screening, not physical design authorization",
        "subsystems": [{"subsystem_id": "enclosure", "name": "Enclosure",
                        "domain": "mechanical"}],
        "components": [],
        "constraints": [],
        "evidence": [],
    }
    for family, source in SOURCES.items():
        component_id = f"candidate-{family}"
        project["components"].append({
            "component_id": component_id,
            "name": source["material_id"],
            "domain": "mechanical",
            "subsystem_id": "enclosure",
            "metadata": {"material_id": source["material_id"]},
        })
        for load, temp_c in source["heat_deflection_c"].items():
            constraint_id = f"hdt-{str(load).replace('.', 'p')}-{family}"
            threshold = next((limit for requested_load, limit in criteria
                              if load == requested_load), None)
            if threshold is None:
                continue
            project["constraints"].append({
                "constraint_id": constraint_id,
                "name": f"ISO75 {load:g} MPa HDT screening criterion",
                "domain": "mechanical",
                "statement": f"HDT at {load:g} MPa >= {threshold:g} C (screening only)",
                "applies_to": [component_id],
                "metadata": {
                    "material_property": "heat_deflection_temperature",
                    "unit": "K",
                    "min_value": threshold + 273.15,
                    "test_method": "ISO 75",
                    "measurement_conditions": {"test_load_mpa": load},
                },
            })
            project["evidence"].append({
                "evidence_id": f"prusa-tds-{family}-{str(load).replace('.', 'p')}",
                "kind": "manufacturer_datasheet",
                "basis": "transcribed_typical_test_value",
                "ref": source["url"],
                "supports": [component_id, constraint_id],
                "authority": "observed",
                "metadata": {
                    "material_id": source["material_id"],
                    "material_property": "heat_deflection_temperature",
                    "unit": "K",
                    "value": temp_c + 273.15,
                    "test_method": "ISO 75",
                    "measurement_conditions": {"test_load_mpa": load},
                    "source_sha256": source["sha256"],
                    "source_page_number": 2,
                    "source_table": "Typical material properties",
                    "extraction_method": "manually_transcribed_from_manufacturer_pdf",
                },
            })
    if include_electrical:
        for family, source in SOURCES.items():
            project["constraints"].append({
                "constraint_id": f"insulation-{family}",
                "name": "Electrical insulation safety criterion",
                "domain": "electrical",
                "statement": "The final geometry/material must have measured insulation evidence",
                "applies_to": [f"candidate-{family}"],
                "metadata": {
                    "material_property": "electrical_resistivity",
                    "unit": "ohm*m",
                    "min_value": 1e9,
                },
            })
    return project


def cases() -> list[dict]:
    first = make_project()
    highload = make_project(stress_criteria=[(0.45, 100), (1.8, 100)])
    mismatch = copy.deepcopy(first)
    for row in mismatch["evidence"]:
        if row["evidence_id"] == "prusa-tds-pc_blend-1p8":
            row["metadata"]["measurement_conditions"]["test_load_mpa"] = 0.45
    invalid_digest = copy.deepcopy(first)
    for row in invalid_digest["evidence"]:
        if row["evidence_id"] == "prusa-tds-pc_blend-0p45":
            row["metadata"]["source_sha256"] = "not-sha256"
    missing_source = copy.deepcopy(first)
    for row in missing_source["evidence"]:
        if row["evidence_id"] == "prusa-tds-pc_blend-0p45":
            row["ref"] = None
    conflict = copy.deepcopy(first)
    second = next(row for row in conflict["evidence"]
                  if row["evidence_id"] == "prusa-tds-pc_blend-0p45")
    revised = copy.deepcopy(second)
    revised["evidence_id"] = "fake-conflicting-revision"
    revised["metadata"]["value"] -= 8
    revised["ref"] = "https://example.invalid/datasheet-conflicting-revision"
    conflict["evidence"].append(revised)
    wrong_method = copy.deepcopy(first)
    for row in wrong_method["evidence"]:
        if row["evidence_id"] == "prusa-tds-pc_blend-0p45":
            row["metadata"]["test_method"] = "ISO 527"
    identity_swap = copy.deepcopy(first)
    for row in identity_swap["evidence"]:
        if row["evidence_id"] == "prusa-tds-pc_blend-0p45":
            row["metadata"]["material_id"] = "Prusament ASA"
    unequal_criteria = copy.deepcopy(first)
    unequal_criteria["constraints"] = [
        row for row in unequal_criteria["constraints"]
        if row["constraint_id"] != "hdt-1p8-pc_blend"
    ]
    unequal_criteria["evidence"] = [
        row for row in unequal_criteria["evidence"]
        if row["evidence_id"] != "prusa-tds-pc_blend-1p8"
    ]
    result = [
        {"case_id": "base_low_stress", "project": first,
         "expected": {"candidate-asa": "blocked", "candidate-pc_blend": "numerically_consistent_but_unverified"}},
        {"case_id": "high_load_100C", "project": highload,
         "expected": {"candidate-asa": "blocked", "candidate-pc_blend": "blocked"}},
        {"case_id": "missing_electrical", "project": make_project(include_electrical=True),
         "expected": {"candidate-asa": "blocked", "candidate-pc_blend": "blocked"}},
    ]
    for name, project in [
        ("wrong_test_load", mismatch), ("tampered_digest", invalid_digest),
        ("missing_reference", missing_source), ("source_disagreement", conflict),
        ("wrong_test_method", wrong_method), ("wrong_material_identity", identity_swap)
    ]:
        result.append({
            "case_id": name, "project": project,
            "expected": {"candidate-asa": "blocked", "candidate-pc_blend": "blocked"},
        })
    result.append({
        "case_id": "incomparable_criteria", "project": unequal_criteria,
        "expected": {"candidate-asa": "blocked",
                     "candidate-pc_blend": "numerically_consistent_but_unverified"},
        "expected_comparable": False,
    })
    return result


def run() -> dict:
    app = TestClient(create_product_app())
    rows = []
    for case in cases():
        started = time.perf_counter()
        response = app.post("/v1/engineering/chemical/materials/compare",
                            json={"project": case["project"],
                                  "component_ids": ["candidate-asa", "candidate-pc_blend"]})
        duration_ms = (time.perf_counter() - started) * 1000
        if response.status_code != 200:
            rows.append({"case_id": case["case_id"], "passed": False,
                         "status_code": response.status_code, "error": response.text[:1000]})
            continue
        report = response.json()
        actual = {row["component_id"]: row["screening_status"]
                  for row in report["summary"]}
        expected_comparable = case.get("expected_comparable", True)
        passed = (actual == case["expected"] and not report["selection_authorized"]
                  and report["comparable_numeric_criteria"] == expected_comparable
                  and (expected_comparable or
                       not report["candidates_requiring_investigation"]))
        rows.append({
            "case_id": case["case_id"],
            "passed": passed, "expected": case["expected"], "actual": actual,
            "duration_ms": round(duration_ms, 2),
            "criteria_comparable": report["comparable_numeric_criteria"],
            "comparison_blockers": report["comparison_blockers"],
            "per_candidate": {
                row["component_id"]: {
                    "blockers": row["blockers"],
                    "passed_numeric_criteria": row["passed_numeric_criteria"],
                    "checked_constraint_count": row["checked_constraint_count"],
                } for row in report["summary"]
            },
        })
    return {
        "schema_version": "hardware_splicer.chemical_material_benchmark.v1",
        "source_data": [
            {"material_id": source["material_id"], "url": source["url"],
             "sha256": source["sha256"], "pdf_page_number": 2,
             "extraction_method": "manual_value_transcription"}
            for source in SOURCES.values()
        ],
        "sample_count": len(rows),
        "passed_count": sum(row["passed"] for row in rows),
        "accuracy": sum(row["passed"] for row in rows) / len(rows),
        "scenarios": rows,
        "scope_limits": [
            "Deliberately constructed cases; not a blinded benchmark.",
            "Manufacturer datasheets are real; screening thresholds are hypothetical.",
            "Source PDFs manually inspected and SHA-pinned; no automated extraction.",
            "No physical safety, compatibility, fabrication or release authority.",
        ],
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["passed_count"] != result["sample_count"]:
        raise SystemExit(1)
