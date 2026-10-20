"""Opt-in end-to-end Prusa PDF -> HS stored source -> claim -> evidence candidate -> screen.

Run after placing original PDFs in an offline temporary directory. Does not
persist to user's project store or alter main. All claims remain proposed.
"""
from __future__ import annotations

import base64
import json
import re
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore
from prusa_enclosure_screen_v1 import SOURCES, make_project
from verify_prusa_tds import FILENAMES, verify_source_files

ROW_PATTERN = re.compile(
    r"Heat\s+Deflection\s+Temperature\s*\(\s*"
    r"(0[.]45|1[.]80)\s*MPa\s*\)\s*\[\s*°C\s*\]"
    r"\s*(\d+)\s+ISO\s+75"
)


def check_response(response, expected=200):
    if response.status_code != expected:
        raise ValueError(f"Unexpected HTTP {response.status_code}: {response.text[:1200]}")
    return response.json()


def run(source_dir: Path) -> dict:
    digest_report = verify_source_files(source_dir)
    if digest_report["verified_count"] != 2:
        raise ValueError("Refusing simulation if original PDF digests or quoted values don't match")

    with tempfile.TemporaryDirectory(prefix="hs-chemical-source-e2e-") as scratch:
        store = ProjectStore(Path(scratch))
        app = TestClient(create_product_app(store))
        project_id = "prusa-materials-e2e"
        first = check_response(
            app.put(f"/v1/projects/{project_id}/snapshot", json={
                "snapshot": {"projectId": project_id, "projectName": "isolated materials review"},
                "expected_revision": 0,
            })
        )
        revision = first["project"]["revision"]
        candidates = []
        for family, source in SOURCES.items():
            contents = (source_dir / FILENAMES[family]).read_bytes()
            ingested = check_response(
                app.post(f"/v1/projects/{project_id}/sources/ingest", json={
                    "filename": FILENAMES[family],
                    "content_base64": base64.b64encode(contents).decode("ascii"),
                    "declared_media_type": "application/pdf",
                    "authority_ceiling": "declared",
                    "expected_revision": revision,
                }),
                201,
            )
            revision = ingested["revision"]
            source_id = ingested["ingestion"]["source_id"]
            doc = check_response(app.get(
                f"/v1/projects/{project_id}/sources/{source_id}/document"
            ))
            if not doc["document"]["extraction"]["source_hash_reverified"]:
                raise ValueError("Source hash verification missing in canonical document read")
            page = check_response(app.get(
                f"/v1/projects/{project_id}/sources/{source_id}/document/pages/2"
            ))["page"]["text"]
            lines = [line.strip() for line in page.splitlines()
                     if ROW_PATTERN.search(line)]
            if len(lines) != 2:
                raise ValueError(f"Expected exactly two canonical ISO75 rows for {family}")
            claim_rows = []
            for line in lines:
                match = ROW_PATTERN.search(line)
                assert match is not None
                load = float(match.group(1))
                value = int(match.group(2))
                if source["heat_deflection_c"][load] != value:
                    raise ValueError("Source content and manually curated values disagree")
                claim_rows.append({
                    "claim_id": f"{family}-hdt-{str(load).replace('.', 'p')}",
                    "subject_id": source["material_id"],
                    "predicate": "heat_deflection_temperature",
                    "value": value,
                    "units": "°C",
                    "page_number": 2,
                    "section": "Typical material properties",
                    "supporting_text": line,
                })
            claims = check_response(
                app.post(f"/v1/projects/{project_id}/sources/{source_id}/document/claims",
                         json={"expected_revision": revision, "claims": claim_rows}),
                201,
            )
            revision = claims["revision"]
            for claim in claims["claims"]:
                load = float(ROW_PATTERN.search(claim["metadata"]["supporting_text"]).group(1))
                converted = check_response(app.post(
                    "/v1/engineering/chemical/materials/document-claim/evidence-draft",
                    json={
                        "claim": claim,
                        "component_id": f"candidate-{family}",
                        "constraint_id": f"hdt-{str(load).replace('.', 'p')}-{family}",
                        "material_id": source["material_id"],
                    },
                ))
                if not converted["requires_human_review"] or converted["persisted"]:
                    raise ValueError("Evidence conversion incorrectly upgraded authorization")
                candidates.append(converted["evidence_candidate"])

        machine_project = make_project()
        machine_project["evidence"] = candidates
        screen = check_response(app.post(
            "/v1/engineering/chemical/materials/compare", json={
                "project": machine_project,
                "component_ids": ["candidate-asa", "candidate-pc_blend"],
            }))
        verdict = {row["component_id"]: row["screening_status"] for row in screen["summary"]}
        expected = {
            "candidate-asa": "blocked",
            "candidate-pc_blend": "numerically_consistent_but_unverified",
        }
        if verdict != expected:
            raise ValueError(f"Unexpected material screening outcome: {verdict}")
        if screen["selection_authorized"] or not screen["comparable_numeric_criteria"]:
            raise ValueError("Invalid authority or incomplete comparison")
        final_revision = store.load(project_id)["revision"]
        if final_revision != revision:
            raise ValueError("Read-only screen mutated canonical project store")
        return {
            "schema_version": "hardware_splicer.chemical_material_source_e2e.v1",
            "result": "pass",
            "original_pdf_digests_checked": 2,
            "canonical_document_hash_rechecks": 2,
            "canonical_source_claims_registered_as_proposed": 4,
            "claim_quote_numeric_matches": 4,
            "proposed_material_evidence_created": 4,
            "project_revision": final_revision,
            "canonical_project_store_not_modified_by_material_screen": True,
            "candidate_screening": verdict,
            "material_selection_authorized": False,
            "limits": "Manually selected source claims, not autonomous extraction or physical testing.",
        }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: registered_pdf_end_to_end.py <offline-prusa-source-directory>")
    result = run(Path(sys.argv[1]))
    print(json.dumps(result, indent=2))
