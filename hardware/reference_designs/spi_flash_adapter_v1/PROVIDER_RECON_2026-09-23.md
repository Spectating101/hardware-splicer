# SPI physical-proof provider reconnaissance — 2026-09-23

Status: **quotation / engineering-review reconnaissance only**  
Tracking: `Spectating101/hardware-splicer#105`  
Canonical campaign: `physical_proof_campaign_v1.json`

This note narrows the first external physical-proof contact to providers whose public documentation currently supports custom PCBA functional testing. It is not a provider selection, purchase authorization, fabrication authorization, power-on authorization, or claim that either provider will accept the exact campaign.

## Decision rule

A provider is usable for this campaign only if it can preserve the exact revision-bound assembly state and return evidence adequate for the Hardware-Splicer physical-proof contract. A cheap assembly quote without the required evidence path is not sufficient.

The first contact remains **quote + engineering review only**.

## Candidate A — JLCPCB Standard PCBA + Functional Test

Official source reviewed: `https://jlcpcb.com/help/article/functional-test-service` (updated 2026-09-09).

Publicly documented fit:

- functional test is available for **Standard PCBA** orders;
- testing is performed from the customer's supplied power-on test method;
- JLCPCB asks for product photos or DFM drawings plus detailed test procedure instructions;
- a demonstration video is preferred;
- a first-board test video is typically returned for customer confirmation;
- some test fixtures may be supported after engineering evaluation;
- the page currently advertises an approximate USD 16 engineering fee plus approximately USD 8/hour operator labor, with actual labor evaluated from the order.

What still requires written confirmation for this exact campaign:

1. exact frozen package can be quoted without silent design-file modification;
2. `R1=DNP`, `R4=DNP`, `JP1=open` can be preserved in the initial assembly state;
3. through-hole `J1` and `JP1` handling is compatible with the requested variant;
4. unpowered resistance/continuity/isolation results can be returned as raw measured values;
5. staged current-limited power can follow the campaign topology and limits rather than a generic one-step power-on;
6. measured 3V3 / 1V8 / DUT_1V8 / current values can be returned, not only a pass/fail summary;
7. rail ramp/overshoot or oscilloscope captures can be returned if requested;
8. the operator can preserve the JP1/OE/CS sequence before running the bounded transaction;
9. the only first functional command can be read-only JEDEC `0x9F`, SPI mode 0, 5 MHz;
10. raw SPI evidence / observed JEDEC ID and board/lot identity can be returned;
11. no program, erase, status-write, reset, repair, substitution, or test-procedure change occurs without explicit review.

Current assessment: **credible quotation/review candidate; exact evidence capability unconfirmed**.

## Candidate B — PCBWay PCBA + custom testing

Official sources reviewed:

- `https://www.pcbway.com/pcb-assembly/pcb-assembly-testing.html`
- `https://www.pcbway.com/pcb_prototype/PCB_Assembly_Functional_Testing.html`
- `https://www.pcbway.com/pcb-assembly.html`

Publicly documented fit:

- custom electrical and functional testing is offered for assembled boards;
- the customer is expected to provide a test plan/procedure and acceptance criteria;
- dedicated fixture/jig requirements can be supplied for feasibility review;
- special operating conditions such as voltage, temperature, communications setup, or burn-in requirements can be specified;
- PCBWay describes engineering support for test scope, test instructions, fixture design when needed, instrument setup, report-form preparation, and test workflow;
- PCBA quotation documentation requests Gerber, BOM, and centroid / pick-and-place information, with test/programming methods supplied in the quote when required.

What still requires written confirmation for this exact campaign:

1. exact frozen package and placement/BOM can be ingested without silent design changes;
2. `R1=DNP`, `R4=DNP`, `JP1=open` can be preserved exactly;
3. through-hole assembly state for `J1` and `JP1` is acceptable;
4. cold resistance/continuity/isolation results can be returned with raw values and units;
5. staged current-limited power and connection topology can be followed exactly;
6. rail values plus current-limit state can be returned as measurements;
7. waveform/ramp/overshoot evidence can be captured or returned if quoted;
8. JP1/OE/CS sequencing can be followed before any SPI clocking;
9. the first transaction can be restricted to read-only JEDEC `0x9F`, mode 0, 5 MHz;
10. raw transaction result, observed ID, board identity, instrument/operator identity, and report artifacts can be returned;
11. any repair, substitution, debug intervention, or procedure deviation is reported before being treated as campaign evidence.

Current assessment: **credible quotation/review candidate; exact evidence capability unconfirmed**.

## Required first-contact payload

Send the same bounded package to both providers so their answers remain comparable:

- exact deterministic remote-FCT package / package checksum;
- schematic PDF and fabrication package;
- BOM and placement files;
- assembly drawing and explicit initial DNP/open state;
- `SPI_PHYSICAL_PROOF_OPERATOR_PACKET.md`;
- `PROVIDER_REVIEW_RECORD.template.json`;
- acceptance criteria / bounded host-test description;
- a statement that the request is for **quotation + engineering feasibility review**, not fabrication authorization.

Ask both providers to return:

- package/revision they reviewed;
- DFM/DFA/component concerns;
- whether any file would need modification;
- exact assembly assumptions;
- cold-test capability and evidence format;
- controlled-power capability and evidence format;
- functional-test capability and fixture/NRE assumptions;
- whether raw measurements/captures can be returned;
- minimum quantity, quote, NRE/fixture cost, and lead time;
- steps requiring explicit customer approval.

## Selection gate

Do not select by price alone. Compare at least:

| Dimension | Requirement |
|---|---|
| Revision fidelity | Exact supplied package remains identifiable. |
| Assembly fidelity | DNP/open/THT assumptions are explicit. |
| Cold evidence | Raw values are available, not only pass/fail. |
| Power discipline | Staged current-limited procedure is accepted. |
| Functional boundary | `0x9F` only for first transaction. |
| Evidence return | Board identity + measurements + raw artifacts can be bound to the run. |
| Change control | No silent repair/substitution/procedure change. |
| Commercial | Quote, NRE, quantity and lead time are explicit. |

If neither provider can return the evidence needed by the campaign, do not weaken the campaign to fit the provider. Escalate to a remote lab / university lab / independent operator route instead.

## Authority effect

`NONE`

Public service descriptions, quotations, engineering replies, DFM comments, and provider capability claims are evidence inputs only. They do not set:

- `provider_selected=true`;
- `fabrication_authorized=true`;
- `power_on_authorized=true`;
- `functional_test_authorized=true`;
- `release_authorized=true`.
