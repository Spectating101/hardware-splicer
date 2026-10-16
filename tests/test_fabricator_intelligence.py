from __future__ import annotations

from fastapi.testclient import TestClient

from hardware_splicer.engineering_artifact_store import EngineeringArtifactStore
from hardware_splicer.fabricator_intelligence_manifest import fabricator_intelligence_manifest
from hardware_splicer.fabricator_intelligence_workbench import FabricatorIntelligenceWorkbench
from hardware_splicer.physical_observation_store import PhysicalObservationStore
from hardware_splicer.procurement_quotes import ProcurementQuoteBook
from hardware_splicer.product_api import create_product_app
from hardware_splicer.vision_inspection import VisionClaim, VisionInspectionService


class FakeVisionProvider:
    model_id = "inspection-model"
    model_version = "1.0"

    def infer(self, *, image: bytes, media_type: str, task_id: str):
        assert image == b"fake-image-bytes"
        assert media_type == "image/png"
        assert task_id == "print_surface"
        return [
            VisionClaim(
                label="possible_corner_lift",
                confidence=0.82,
                description="Lower-left edge may be lifted relative to the expected plane.",
                region=(0.0, 0.7, 0.25, 1.0),
            )
        ]


def test_vision_claim_is_bound_to_exact_observation_but_not_physical_evidence(tmp_path):
    observations = PhysicalObservationStore(tmp_path / "observations")
    raw = observations.put(
        kind="image",
        source_id="bench-camera",
        media_type="image/png",
        data=b"fake-image-bytes",
    )
    artifacts = EngineeringArtifactStore(tmp_path / "artifacts")
    service = VisionInspectionService(
        observations=observations,
        artifacts=artifacts,
        provider=FakeVisionProvider(),
    )
    result = service.inspect(
        observation_id=raw.observation_id,
        task_id="print_surface",
        output_artifact_id="inspection-v1",
    )
    inspection = result["inspection"]
    assert inspection["observation_sha256"] == raw.sha256
    assert inspection["claims"][0]["confidence"] == 0.82
    assert inspection["evidence_class"] == "model_inference"
    assert inspection["hypothesis_only"] is True
    assert inspection["passes_validation"] is None
    assert inspection["may_auto_promote_to_physical_evidence"] is False
    assert inspection["grants_physical_authority"] is False
    assert result["artifact"]["kind"] == "inspection_document"
    assert result["artifact"]["executable"] is False


def _quotes() -> ProcurementQuoteBook:
    quotes = ProcurementQuoteBook()
    quotes.add(
        quote_id="q-mcu-a",
        supplier_id="supplier-a",
        part_key="mcu",
        currency="USD",
        unit_price="4.50",
        stock_quantity=100,
        lead_time_days=2,
        source_ref="supplier-a-snapshot-1",
        observed_at="2026-10-17T00:00:00+00:00",
    )
    quotes.add(
        quote_id="q-mcu-b",
        supplier_id="supplier-b",
        part_key="mcu",
        currency="USD",
        unit_price="4.00",
        minimum_order_quantity=10,
        stock_quantity=1000,
        lead_time_days=5,
        source_ref="supplier-b-snapshot-1",
        observed_at="2026-10-17T00:00:00+00:00",
    )
    quotes.add(
        quote_id="q-sensor",
        supplier_id="supplier-a",
        part_key="sensor",
        currency="USD",
        unit_price="3.25",
        stock_quantity=25,
        lead_time_days=3,
        source_ref="supplier-a-snapshot-2",
        observed_at="2026-10-17T00:00:00+00:00",
    )
    return quotes


def test_procurement_costing_respects_moq_and_does_not_purchase():
    estimate = _quotes().cost_bom(
        lines=[{"part_key": "mcu", "quantity": 2}, {"part_key": "sensor", "quantity": 1}],
        currency="USD",
        as_of="2026-10-17T01:00:00+00:00",
    )
    # Supplier A wins MCU despite supplier B's lower unit price because B's MOQ is 10.
    mcu = next(row for row in estimate["lines"] if row["part_key"] == "mcu")
    assert mcu["selected_quote_id"] == "q-mcu-a"
    assert estimate["estimated_total"] == "12.25"
    assert estimate["price_guaranteed"] is False
    assert estimate["stock_guaranteed"] is False
    assert estimate["purchase_authorized"] is False
    assert estimate["order_submitted"] is False


def test_tradeoff_returns_pareto_frontier_not_magic_winner():
    workbench = FabricatorIntelligenceWorkbench(procurement=_quotes())
    comparison = workbench.compare_options(
        options=[
            {
                "option_id": "clean",
                "kind": "clean_sheet",
                "bom": [{"part_key": "mcu", "quantity": 1}, {"part_key": "sensor", "quantity": 1}],
                "unresolved_evidence": 0,
                "fabrication_operations": 2,
                "manual_steps": 5,
                "donor_dependencies": 0,
            },
            {
                "option_id": "reclaim",
                "kind": "reclaim_heavy",
                "bom": [{"part_key": "sensor", "quantity": 1}],
                "unresolved_evidence": 3,
                "fabrication_operations": 1,
                "manual_steps": 8,
                "donor_dependencies": 2,
            },
            {
                "option_id": "bad",
                "kind": "hybrid",
                "bom": [{"part_key": "mcu", "quantity": 1}, {"part_key": "sensor", "quantity": 1}],
                "unresolved_evidence": 2,
                "fabrication_operations": 4,
                "manual_steps": 10,
                "donor_dependencies": 1,
            },
        ],
        currency="USD",
        as_of="2026-10-17T01:00:00+00:00",
    )
    assert comparison["automatic_winner"] is None
    assert comparison["decision_requires_policy_or_human"] is True
    assert "bad" not in comparison["pareto_frontier"]
    assert set(comparison["pareto_frontier"]) == {"clean", "reclaim"}


def test_agent_api_has_no_quote_ingestion_or_physical_evidence_promotion_route():
    quotes = _quotes()
    workbench = FabricatorIntelligenceWorkbench(procurement=quotes)
    app = create_product_app(fabricator_intelligence_workbench=workbench)
    client = TestClient(app)
    listed = client.get("/v1/fabricator/intelligence/procurement/quotes")
    assert listed.status_code == 200
    assert len(listed.json()["quotes"]) == 3
    paths = set(app.openapi()["paths"])
    assert "/v1/fabricator/intelligence/procurement/quotes" in paths
    assert "/v1/fabricator/intelligence/procurement/quotes/ingest" not in paths
    assert "/v1/fabricator/intelligence/vision/promote" not in paths


def test_intelligence_routes_fail_closed_and_manifest_states_authority_boundary():
    app = create_product_app()
    client = TestClient(app)
    response = client.get("/v1/fabricator/intelligence/procurement/quotes")
    assert response.status_code == 503
    manifest = fabricator_intelligence_manifest(app)
    assert manifest["authority_contract"]["vision_model_can_pass_physical_validation"] is False
    assert manifest["authority_contract"]["agent_can_ingest_supplier_quotes"] is False
    assert manifest["authority_contract"]["agent_can_purchase"] is False
    assert manifest["authority_contract"]["tradeoff_has_automatic_winner"] is False
