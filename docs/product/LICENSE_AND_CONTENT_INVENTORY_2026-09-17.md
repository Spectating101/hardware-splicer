# Hardware Splicer license and content inventory — preparation draft

**Purpose:** determine what may be included in an open archive and what must be resolved before OSHWA self-certification.  
**Effect:** inventory only. This file does not change any license or make a legal certification.

## Current repository declaration

The repository root contains an MIT license identifying `Spectating101 / Hardware-Splicer contributors`. The README describes that license as the software license.

That is adequate evidence of an intended MIT software license. It does not by itself resolve whether every hardware design file, document, screenshot, dataset, vendor datasheet, historical asset, or third-party fixture is creator-controlled or appropriately licensed for an open archive or OSHWA certification.

## Proposed scope map for human approval

| Scope | Current observation | Proposed treatment | Gate |
|---|---|---|---|
| First-party software under `src/`, scripts, tests, API/MCP and first-party apps | root MIT declaration | retain MIT | confirm contributor/ownership scope |
| First-party SPI KiCad design, BOM, manifests and generated fabrication data | public and editable; no hardware-specific license notice found | apply an OSHWA-compatible open-hardware license such as CERN-OHL-P-2.0 if the owner approves | human legal/license decision |
| First-party product and engineering documentation | root MIT is present but documentation scope is not explicit | use CC BY 4.0 or CC BY-SA 4.0 if the owner approves | human legal/license decision |
| Project-local KiCad symbols derived from public manufacturer pinouts | first-party file, factual manufacturer identity embedded | include under approved hardware/design scope with source attribution | provenance review |
| KiCad standard libraries | referenced from the installed toolchain, not copied into the SPI directory | do not relicense; preserve tool/version references | none for current archive |
| Freerouting | external pinned tool, binary not required in repository archive | link to upstream and record version/hash; do not redistribute unless its license package is preserved | archive assembly review |
| `examples/kicad_pcb_fixtures/` | contains its own GPLv3 license text | preserve GPLv3 scope and notice | verify boundary in archive manifest |
| Vendor datasheets under `apps/circuit-ai/data/datasheets/` | numerous third-party PDF files from TI, Winbond and others | exclude from Zenodo/open artifact unless redistribution terms are individually verified; keep source URLs/identities instead | required exclusion |
| `apps/circuit-ai/assets/analysis_1.pdf` | provenance/license not established by this audit | exclude until reviewed | required exclusion |
| Historical competition PDFs and generated proposal PDFs | may contain first-party text plus fonts/templates/logos with separate terms | exclude from canonical technical archive unless individually cleared | required exclusion |
| Third-party model/provider responses or downloaded manufacturer models | provider/vendor terms may restrict redistribution | include hashes, metadata and permitted derived receipts; exclude raw restricted bytes | terms review |
| Screenshots under repository/review directories | likely first-party captures but may contain third-party UI/logos/data | include only selected captures after content review | media review |

## Known third-party concentration

The highest-risk tracked content is the datasheet collection under:

```text
apps/circuit-ai/data/datasheets/
```

It contains third-party manufacturer PDFs and should not be swept into a Zenodo deposit merely because the repository is public.

Other content requiring explicit review includes:

- competition/proposal PDFs;
- downloaded or captured manufacturer-model bytes;
- generated screenshots containing third-party interfaces;
- historical archives under `releases/`;
- fixtures with their own GPLv3 scope.

## Safe initial archive boundary

The first Zenodo candidate should be the already published, byte-bound SPI remote-FCT release plus first-party metadata—not a full repository snapshot assembled without exclusions.

Include after review:

- the published release ZIP;
- `SHA256SUMS.txt`;
- package handoff;
- current product landing document;
- claims/nonclaims statement;
- approved citation metadata;
- approved license notices specific to included content.

Exclude initially:

- the repository-wide vendor datasheet collection;
- raw third-party model files without redistribution permission;
- unrelated historical binaries and proposals;
- secrets, account data, contact details, and ignored provider outputs.

## Decisions required

1. Confirm the owner/creator name used for licensing and citation.
2. Confirm whether all first-party software contributors may remain under MIT.
3. Select an open-hardware license for creator-controlled design material.
4. Select an open documentation license.
5. Decide whether any patent, employer, university, sponsor, or co-contributor rights constrain relicensing.
6. Approve the exact archive include/exclude manifest.

Until those decisions are made, OSHWA and Zenodo publication remain preparation-only.
