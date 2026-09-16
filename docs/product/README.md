# Hardware Splicer — current product package

**Frozen authority:** `f892facd67c5124e2362860ebc999625afedc5d5`  
**Release:** [`gauntlet-spi-flash-adapter-v1-20260916`](https://github.com/Spectating101/hardware-splicer/releases/tag/gauntlet-spi-flash-adapter-v1-20260916)  
**Package SHA-256:** `6d4c76feaeebdab1223ed6c4be21d63835212baea731aea9d3933f2525be1edd`  
**Physical state:** `PACKAGED_NOT_PHYSICAL`

## What it is

Hardware Splicer is an open engineering workbench for agent-assisted hardware work. An AI agent may inspect evidence, propose changes, use tools, and assemble engineering artifacts; deterministic checks, exact revision identities, provenance-bearing evidence, and explicit human authorization decide what may be accepted or acted on.

> **AI proposes. Deterministic systems check. Physical evidence decides. A human authorizes consequential action.**

The frozen public case is a 3.3 V-host to 1.8 V SPI-flash adapter. It includes editable KiCad sources, a routed two-layer PCB, BOM, placement data, fabrication outputs, verification receipts, bounded host-test software, and a provider-neutral remote-FCT handoff.

It has not been fabricated, assembled, powered, or physically measured.

![Top-layer rendering of the frozen SPI flash adapter](media/spi_flash_adapter_v1-top.svg)

Rendering SHA-256: `bf7685d26c956bcc1886715301d19885b4b4357612ce63f269079d1e39025bc0`.

## Why it exists

A plausible AI answer can reach fabrication or power-on before the component, voltage domain, source, revision, or physical behavior is actually known. Hardware Splicer keeps those questions outside model confidence.

The SPI case makes the distinction concrete:

```text
source evidence
    -> derived simulation
    -> manufacturer-model evidence
    -> editable CAD and deterministic checks
    -> fabrication package
    -> physical measurement
```

Evidence at one layer does not silently acquire authority at the next.

## What is available now

| Surface | Current evidence |
|---|---|
| Canonical software/API/MCP system | implemented and covered by exact-head CI |
| Frozen adversarial SPI corpus | ten cases and deterministic validation infrastructure exist |
| Primary-source agent demonstration | one bounded Astra run exists as an existence demonstration |
| Full cross-condition reliability result | not yet established |
| SPI reference design | editable schematic/PCB, BOM, fabrication and assembly outputs packaged |
| CAD consistency | ERC/DRC/parity and bound design checks pass |
| Provider/FCT handoff | deterministic, self-auditing package published |
| Fabrication and physical testing | not performed |
| Independent operator evidence | not established |
| Production readiness | not claimed |

## Evaluate it in five minutes

1. Read the [claims and nonclaims](../external_assessment/CLAIMS_AND_NONCLAIMS.md).
2. Verify the [published release](https://github.com/Spectating101/hardware-splicer/releases/tag/gauntlet-spi-flash-adapter-v1-20260916) against its SHA-256 file.
3. Inspect the [SPI reference design](../../hardware/reference_designs/spi_flash_adapter_v1/README.md).
4. Review the [offline demonstration](OFFLINE_DEMO.md).
5. Inspect the [evidence ledger](../external_assessment/EVIDENCE_LEDGER.md) and [remote-FCT campaign](../external_assessment/proof/SPI_REMOTE_FCT_CAMPAIGN.md).

For common maturity, licensing, citation, and fabrication questions, see the [FAQ](FAQ.md) and [evidence map](EVIDENCE_MAP.md).

## Reproduce the reference-design checks

Prerequisites are Python 3 and KiCad 9. From the repository root:

```bash
cd hardware/reference_designs/spi_flash_adapter_v1
python3 verify_design.py
python3 build_package.py --output out/spi-flash-adapter-v1-review-package.zip
python3 build_remote_fct_campaign.py --output out/spi-flash-adapter-v1-remote-fct.zip
```

The build scripts normalize timestamps and audit the resulting packages. A successful software build does not authorize fabrication or power-on.

## Choose the view that matches your role

- **Embedded/open-source engineer:** start here, then inspect the reference design and offline demo.
- **Hardware reviewer:** use the reference-design README, BOM, verification receipt, acceptance criteria, and controlled physical handoff.
- **Fabricator/FCT provider:** use only the provider-neutral quotation/FCT packet after the owner authorizes contact.
- **Research reviewer:** use the [research protocol](../external_assessment/research_access/CORE_RESEARCH_PROTOCOL.md), frozen corpus, trace requirements, and evidence ledger.
- **Conference reviewer:** use the current route packet under [`routes/`](routes/); do not infer a different physical state from route-specific wording.

## Current conversion package

- [Audience and message system](AUDIENCE_AND_MESSAGE_SYSTEM.md)
- [Evidence map](EVIDENCE_MAP.md)
- [FAQ](FAQ.md)
- [Machine-readable claims and nonclaims](claims-and-nonclaims.v1.json)
- [Packaging QA](PACKAGING_QA_2026-09-17.md)
- [License and content inventory](LICENSE_AND_CONTENT_INVENTORY_2026-09-17.md)
- [OSHWA preparation checklist](OSHWA_PREPARATION_CHECKLIST_2026-09-17.md)
- [Archive/DOI deposit draft](ARCHIVE_DEPOSIT_DRAFT_2026-09-17.md)
- [Machine-readable archive manifest](archive-manifest.v1.json)
- [Offline demonstration](OFFLINE_DEMO.md)
- [Provider handoff QA](PROVIDER_HANDOFF_QA_2026-09-17.md)
- [Evaluation execution freeze](EVALUATION_EXECUTION_FREEZE_2026-09-17.md)
- [Evaluation readiness record](evaluation-readiness.v1.json)
- [Frozen adjudication guide](ADJUDICATION_GUIDE_2026-09-17.md)
- [Embedded World 2027 packet](routes/EMBEDDED_WORLD_2027.md)

## Claim ceiling

Do not describe the frozen candidate as physically validated, fabrication-authorized, production-ready, independently validated, OSHWA-certified, peer-reviewed, or externally deployed. Those states require separate external receipts and, for physical claims, revision-bound measurements.
