# Fabricator intelligence

This layer adds decision support above the fabrication digital thread without allowing model output or supplier data to become physical truth or purchasing authority.

## Visual inspection

`VisionInspectionService` runs an injected vision provider only against an already-retained `PhysicalObservationStore` image. Every inference is bound to the exact observation SHA-256, model id/version and task id.

Outputs are deliberately classified as `model_inference` and `hypothesis_only=true`. The service has no path that turns a model claim into a passed/failed `PhysicalEvidenceRecord`. A later validation procedure may use the inference to decide what to measure or inspect, but measurement/evidence promotion remains separate.

The public API accepts only:

- retained observation id;
- bounded inspection task id;
- output inspection artifact id.

Raw image bytes and arbitrary provider configuration are not accepted from the agent surface.

## Procurement snapshots

`ProcurementQuoteBook` stores immutable quote snapshots with:

- supplier and part identities;
- optional manufacturer part number;
- currency and decimal unit price;
- minimum order quantity;
- observed stock quantity;
- observed lead time;
- observed/expiry timestamps;
- source reference.

Agent-facing routes are read/estimate only. There is intentionally no quote-ingestion, checkout, payment, shipping or order route.

`cost_bom()` accounts for MOQ, known stock and quote expiry and marks all results as estimates. Price and stock are never guaranteed from a snapshot.

## Clean / reclaim / hybrid tradeoffs

`FabricationOptionTradeoff` accepts candidate descriptions that can later be populated by P4/P5 donor and reverse-engineering work. For each option it carries separate dimensions instead of collapsing uncertainty into one opaque score:

- unpriced BOM lines;
- quoted procurement total;
- maximum quoted lead time when known;
- unresolved evidence count;
- fabrication operation count;
- manual step count;
- donor dependency count.

The result is a Pareto frontier and dominance map. `automatic_winner` is always null; policy/human/mission reasoning decides among non-dominated alternatives.

## Canonical agent surface

`/v1/fabricator/intelligence/*` is fail-closed until a server-owned `FabricatorIntelligenceWorkbench` is configured.

Bounded operations:

- inspect a retained image;
- list provider/server-ingested quote snapshots;
- estimate BOM procurement;
- compare architecture tradeoffs.

The corresponding MCP/OpenAPI projection is `fabricator_intelligence_manifest()`.
