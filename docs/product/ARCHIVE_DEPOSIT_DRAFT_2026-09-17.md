# Hardware Splicer archive/DOI deposit draft

**State:** metadata and payload preparation only; no external record has been created or published.

## Proposed record

**Title:** Hardware Splicer — SPI Flash Adapter Remote-FCT Open Verification Artifact  
**Version:** 2026.09.1  
**Resource type:** Software / open hardware engineering artifact  
**Publication date:** use the actual deposit publication date  
**Creator:** Christopher Ongko — confirm public citation form and ORCID before publication  
**Repository:** https://github.com/Spectating101/hardware-splicer  
**Frozen source:** `f892facd67c5124e2362860ebc999625afedc5d5`  
**Release tag:** `gauntlet-spi-flash-adapter-v1-20260916`

## Proposed description

Hardware Splicer is an evidence-gated workbench for agent-assisted hardware engineering. This record freezes the SPI Flash Adapter Remote-FCT candidate at an internally verified, pre-fabrication boundary. It contains editable and generated design artifacts, manufacturing and assembly inputs, deterministic verification receipts, bounded host-test software, acceptance criteria, and an evidence-return contract. The artifact is `PACKAGED_NOT_PHYSICAL`: no board has been fabricated, assembled, powered, or physically validated, and no production-readiness claim is made.

## Keywords

- agentic hardware engineering
- open hardware
- hardware verification
- electronic design automation
- evidence provenance
- SPI flash
- KiCad
- functional test
- human-in-the-loop

## Proposed payload

| File | Identity | State |
|---|---|---|
| `spi-flash-adapter-v1-remote-fct-main-f892fac.zip` | SHA-256 `6d4c76feaeebdab1223ed6c4be21d63835212baea731aea9d3933f2525be1edd` | published GitHub release asset; verified locally |
| `SHA256SUMS.txt` | published release asset | include |
| `PACKAGE_HANDOFF.md` | published release asset | include |
| `PRODUCT_README.md` | projection of `docs/product/README.md` | prepare |
| `CLAIMS_AND_NONCLAIMS.md` | canonical claim boundary | reconcile current release before inclusion |
| `CITATION.cff` | derived from `docs/product/CITATION.cff.draft` | human identity review required |
| license files/notices | exact included scopes | human license decision required |

## Exclusions

- repository-wide third-party datasheet PDFs;
- raw vendor/model bytes without confirmed redistribution permission;
- unrelated historical release archives;
- account, contact, provider, payment, or secret material;
- ignored quotation/reviewer packets;
- any claimed DOI, SWHID, OSHWA UID, fabrication result, or physical measurement that does not yet exist.

## DOI workflow

1. Approve creator identity, optional ORCID, licenses, and include/exclude manifest.
2. Create a draft deposit without publishing.
3. Upload the exact payload and compare Zenodo-reported checksums.
4. Review the rendered record and claim boundary.
5. Human publishes the record.
6. Capture DOI, record URL, publication timestamp, file checksums, and receipt.
7. Add the real DOI to root `CITATION.cff` and the product landing page in a new commit/release.

Do not place a reserved or imagined DOI into the frozen release.

## Software Heritage workflow

After public-source scope review, request archival of:

```text
https://github.com/Spectating101/hardware-splicer
```

Capture the real request/visit status and SWHID when issued. A Software Heritage identifier establishes preserved source identity, not engineering correctness.

## Publication gates

- creator identity confirmed;
- archive license choices confirmed;
- third-party exclusions verified;
- checksums match;
- product and claim documents reconciled to the frozen release;
- human authorizes public publication.
