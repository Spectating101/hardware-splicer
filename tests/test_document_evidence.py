from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from hardware_splicer.engineering_source_ingestion import (
    EngineeringSourceIngestionRequest,
    ingest_engineering_source,
)
from hardware_splicer.mcp_backend_gateway import task_operation_manifest
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


def _pdf_bytes(pages: list[str]) -> bytes:
    """Build a tiny text PDF without relying on a fixture file or PDF renderer."""

    page_ids = [4 + (index * 2) for index in range(len(pages))]
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        (
            b"<< /Type /Pages /Kids ["
            + b" ".join(f"{page_id} 0 R".encode() for page_id in page_ids)
            + f"] /Count {len(pages)} >>".encode()
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for index, text in enumerate(pages):
        page_id = page_ids[index]
        content_id = page_id + 1
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("ascii")
        objects.extend(
            [
                (
                    f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                    f"/Resources << /Font << /F1 3 0 R >> >> "
                    f"/Contents {content_id} 0 R >>"
                ).encode("ascii"),
                b"<< /Length "
                + str(len(stream)).encode("ascii")
                + b" >>\nstream\n"
                + stream
                + b"\nendstream",
            ]
        )

    payload = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for object_id, body in enumerate(objects, start=1):
        offsets.append(len(payload))
        payload.extend(f"{object_id} 0 obj\n".encode("ascii"))
        payload.extend(body)
        payload.extend(b"\nendobj\n")
    xref_offset = len(payload)
    payload.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    payload.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        payload.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    payload.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(payload)


def _seed_pdf(store: ProjectStore) -> tuple[str, bytes]:
    content = _pdf_bytes(
        [
            "Absolute Maximum Ratings: any pin shall not exceed VCC plus 0.4 V.",
            "Recommended supply voltage range is 1.7 V to 1.95 V.",
        ]
    )
    ingestion = ingest_engineering_source(
        EngineeringSourceIngestionRequest(
            project_id="doc-case",
            filename="manufacturer-datasheet.pdf",
            content_base64=__import__("base64").b64encode(content).decode("ascii"),
            authority_ceiling="declared",
        ),
        project_root=store.root,
    )
    store.save(
        "doc-case",
        {
            "projectId": "doc-case",
            "projectName": "Document case",
            "engineeringSources": [ingestion.source_descriptor],
        },
        expected_revision=0,
        metadata={"source": "test"},
    )
    return ingestion.source_id, content


def test_document_surface_is_hash_bound_page_addressed_and_read_only(
    tmp_path: Path,
) -> None:
    store = ProjectStore(tmp_path)
    source_id, _content = _seed_pdf(store)
    client = TestClient(create_product_app(store))

    inspected = client.get(f"/v1/projects/doc-case/sources/{source_id}/document")
    searched = client.get(
        f"/v1/projects/doc-case/sources/{source_id}/document/search",
        params={"q": "1.95 V"},
    )
    page = client.get(
        f"/v1/projects/doc-case/sources/{source_id}/document/pages/1"
    )

    assert inspected.status_code == 200
    document = inspected.json()["document"]
    assert document["page_count"] == 2
    assert document["extraction"]["source_hash_reverified"] is True
    assert document["claims_created"] is False
    assert searched.status_code == 200
    assert searched.json()["search"]["matches"][0]["page_number"] == 2
    assert page.status_code == 200
    assert "VCC plus 0.4 V" in page.json()["page"]["text"]
    assert page.json()["page"]["evidence_locator_candidate"][
        "source_content_hash"
    ] == document["content_hash"]
    assert store.load("doc-case")["revision"] == 1


def test_document_claim_requires_page_support_and_persists_as_unreviewed_proposal(
    tmp_path: Path,
) -> None:
    store = ProjectStore(tmp_path)
    source_id, _content = _seed_pdf(store)
    client = TestClient(create_product_app(store))
    payload = {
        "expected_revision": 1,
        "claims": [
            {
                "claim_id": "dut-pin-absolute-max",
                "subject_id": "dut",
                "predicate": "pin_voltage_absolute_max",
                "value": "VCC + 0.4 V",
                "page_number": 1,
                "section": "Absolute Maximum Ratings",
                "supporting_text": (
                    "any pin shall not exceed VCC plus 0.4 V"
                ),
            }
        ],
    }

    response = client.post(
        f"/v1/projects/doc-case/sources/{source_id}/document/claims",
        json=payload,
    )

    assert response.status_code == 201
    assert response.json()["revision"] == 2
    assert response.json()["claim_authority"] == "proposed"
    snapshot = store.load("doc-case")["snapshot"]
    claim = snapshot["engineeringSources"][0]["claims"][0]
    assert claim["authority"] == "proposed"
    assert claim["source_id"] == source_id
    assert claim["evidence_locator"]["page"] == 1
    assert claim["evidence_locator"]["source_content_hash"].startswith("sha256:")
    assert claim["evidence_locator"]["page_text_sha256"].startswith("sha256:")
    assert claim["metadata"]["independent_review_state"] == "unreviewed"

    duplicate = client.post(
        f"/v1/projects/doc-case/sources/{source_id}/document/claims",
        json={**payload, "expected_revision": 2},
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["registered"] is False
    assert store.load("doc-case")["revision"] == 2


def test_document_claim_rejects_unsupported_quote_without_mutation(
    tmp_path: Path,
) -> None:
    store = ProjectStore(tmp_path)
    source_id, _content = _seed_pdf(store)
    client = TestClient(create_product_app(store))

    response = client.post(
        f"/v1/projects/doc-case/sources/{source_id}/document/claims",
        json={
            "expected_revision": 1,
            "claims": [
                {
                    "claim_id": "invented-rating",
                    "subject_id": "dut",
                    "predicate": "pin_voltage_absolute_max",
                    "value": "5 V tolerant",
                    "page_number": 1,
                    "supporting_text": "all pins are 5 V tolerant",
                }
            ],
        },
    )

    assert response.status_code == 422
    assert "not present" in response.json()["detail"]["message"]
    assert store.load("doc-case")["revision"] == 1


def test_document_surface_rejects_blob_tampering(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    source_id, _content = _seed_pdf(store)
    snapshot = store.load("doc-case")["snapshot"]
    source = snapshot["engineeringSources"][0]
    blob = tmp_path / "doc-case" / source["metadata"]["blob_ref"]
    blob.write_bytes(b"%PDF-1.4\ntampered")
    client = TestClient(create_product_app(store))

    response = client.get(
        f"/v1/projects/doc-case/sources/{source_id}/document/pages/1"
    )

    assert response.status_code == 422
    assert "no longer matches" in response.json()["detail"]["message"]


def test_document_grounded_task_manifest_exposes_only_canonical_operations() -> None:
    manifest = task_operation_manifest("document_grounded_pre_fabrication")
    paths = {row["path"] for row in manifest["operations"]}

    assert {
        "/v1/projects/{project_id}/sources/{source_id}/document",
        "/v1/projects/{project_id}/sources/{source_id}/document/search",
        "/v1/projects/{project_id}/sources/{source_id}/document/pages/{page_number}",
        "/v1/projects/{project_id}/sources/{source_id}/document/claims",
        "/v1/projects/{project_id}/engineering/pre-fabrication-plan",
    }.issubset(paths)
    assert manifest["authority_contract"]["projection_grants_physical_authority"] is False
