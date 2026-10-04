# SPI provider manual submission runbook — 2026-09-23

Status: **quote / engineering review only**  
Tracking: `Spectating101/hardware-splicer#105`  
Stack: `Spectating101/hardware-splicer#107`

This runbook describes the human browser/email steps for contacting the two current provider candidates without granting purchase, fabrication, power-on, functional-test, rework, or release authority.

## Shared payload

Use the same frozen subject for both providers:

- release: `gauntlet-spi-flash-adapter-v1-20260916`
- revision: `f892facd67c5124e2362860ebc999625afedc5d5`
- package: `spi-flash-adapter-v1-remote-fct-main-f892fac.zip`
- SHA-256: `6d4c76feaeebdab1223ed6c4be21d63835212baea731aea9d3933f2525be1edd`

Attach/provide, as supported by the provider intake:

- Gerber/fabrication files;
- BOM;
- CPL / centroid / pick-and-place;
- assembly drawing / references;
- `PROVIDER_QUOTE_REQUEST.md`;
- `SPI_PHYSICAL_PROOF_OPERATOR_PACKET.md`;
- explicit R1=DNP, R4=DNP, JP1=open initial state;
- any product/DFM image requested for FCT feasibility.

Do not alter the frozen files merely to satisfy a provider intake parser. Any required normalization or design/manufacturing change must be recorded as a provider finding first.

## JLCPCB — manual quote / feasibility path

Current official flow:

1. Start a PCB / PCBA quote.
2. Upload the Gerber/fabrication package.
3. Enable **PCB Assembly** and use **Standard PCBA**.
4. Upload BOM + CPL and review the component matching and placement.
5. Use **Advanced Options -> Function Test**.
6. Put the bounded test requirements in the special-requirements / remark path and provide the detailed test procedure / DFM or product image requested by the FCT service.
7. Save/review the quote/cart state only.
8. **Stop before Secure Checkout / payment.**
9. If the quote UI cannot carry the complete evidence requirements, send the same inquiry to JLCPCB support and ask engineering to confirm feasibility before any order is paid.

JLCPCB's current FCT service is Standard-PCBA-only, is executed from a customer-provided power-on procedure, and normally returns a first-board test video for customer confirmation. Fixture feasibility is engineering-reviewed.

## PCBWay — manual quote / feasibility path

Current official flow:

1. Open the PCB Assembly quote.
2. Choose the appropriate assembly model; explicitly set **Function test = Yes**.
3. Use **Detailed information of assembly** for the bounded test requirements and no-substitution/no-silent-change rules.
4. Calculate/save the inquiry.
5. Upload Gerber, BOM, Centroid/pick-and-place and the additional assembly/test instruction files.
6. Submit the inquiry for engineering review / final quotation.
7. **Do not proceed to payment or production authorization.**
8. If the web form cannot preserve the full evidence requirements, reference the quote/order number and send the same files/instructions through PCBWay service support.

PCBWay's current quote surface explicitly separates functional test as an advanced option and supports additional assembly files/instructions for review.

## Reply capture

For every reply:

1. preserve the original provider wording and quote/reference ID;
2. populate the matching pending provider review JSON record;
3. do not convert sales language into stronger technical claims;
4. run:
   `python scripts/evaluate_spi_provider_review.py <provider-record.json>`
5. treat only `ELIGIBLE_FOR_HUMAN_DECISION` as permission to *consider* provider selection;
6. `INCOMPLETE` means obtain missing written confirmation;
7. `DISQUALIFIED` means do not select that provider for this campaign unless a new review record resolves the disqualifier.

## Hard stop

The following actions remain human-only and outside this runbook:

- selecting the winning provider;
- committing payment;
- authorizing fabrication/assembly;
- authorizing power-on;
- authorizing the bounded SPI transaction;
- accepting rework/substitution;
- releasing any physical result.

A complete quote is evidence for a decision. It is not the decision.
