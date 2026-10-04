# SPI Flash Adapter v1 — quotation + engineering feasibility request

Status: **pre-fabrication inquiry only**  
Campaign: `hs-spi-physical-proof-v1`  
Tracking: `Spectating101/hardware-splicer#105`

This request is designed to be sent unchanged to candidate PCBA/FCT providers so their responses can be compared against the same revision-bound requirements.

## Request

We have a small two-layer SPI flash adapter PCB that is ready for quotation and engineering feasibility review. We are **not authorizing fabrication or test through this message**. We first need confirmation that your assembly and functional-test workflow can preserve the supplied revision and return the measurements required by our validation procedure.

The supplied package contains the fabrication files, BOM, placement data, schematic/assembly references, deterministic package identity, and a bounded physical-validation procedure.

### Frozen package identity

- Release: `gauntlet-spi-flash-adapter-v1-20260916`
- Source revision: `f892facd67c5124e2362860ebc999625afedc5d5`
- Package: `spi-flash-adapter-v1-remote-fct-main-f892fac.zip`
- SHA-256: `6d4c76feaeebdab1223ed6c4be21d63835212baea731aea9d3933f2525be1edd`

Please confirm the package digest before engineering review. If your intake system regenerates, modifies, or normalizes any design/manufacturing file, identify that change explicitly before the result is treated as campaign evidence.

### Initial assembly state

Please confirm that the initial assembly can preserve these states exactly:

- `R1` — DNP / not fitted;
- `R4` — DNP / not fitted;
- `JP1` header fitted, but **no shunt installed**;
- J1 / JP1 through-hole handling as specified by the package;
- no component substitution, footprint modification, repair, or design-file modification without written customer review.

If any supplied item, footprint, drill, clearance, stackup, assembly instruction, or component availability creates a DFM/DFA concern, please return the finding before changing the files or assembly state.

## Requested test feasibility

Please indicate which of the following you can perform and what raw evidence/report you can return.

### 1. Unpowered checks

Before power is applied, we need revision-bound resistance / continuity / isolation checks, including the specified supply-domain isolation, OE pull-down, and CS-domain pull-up conditions.

Please state whether you can return:

- measured values and units rather than only pass/fail;
- board/lot identity;
- instrument identity where available;
- operator/test-station identity where available;
- raw test logs or report files.

### 2. Controlled power

The board must be powered in stages using the supplied connection topology and current limits. Please state whether you can:

- apply the specified current-limited supply sequence;
- return measured 3V3, 1V8 / DUT_1V8, current, and current-limit state;
- capture rail ramp / overshoot / timing with an oscilloscope when requested;
- return the underlying measurements/captures, not only an overall pass/fail result.

### 3. Bounded functional test

Only after the previous gates pass, the first functional transaction is deliberately restricted to:

- SPI mode 0;
- 5 MHz;
- read-only command `0x9F` (JEDEC ID);
- expected response `EF6018`.

Program, erase, status-write, reset, or other modifying commands are outside this first validation procedure.

Please confirm whether your test workflow can preserve the supplied JP1 / OE / CS sequence and return the observed JEDEC ID plus raw transaction evidence/logs where available.

## Evidence and change control

For this campaign, a provider pass/fail label by itself is not enough. We need the result tied to the exact board and supplied revision.

Please confirm whether your return package can identify:

- exact customer package/revision reviewed or built;
- physical board or lot identity;
- assembly variant/state;
- test date;
- raw or structured measurement results;
- photographs or test video if available;
- waveform/log files if quoted;
- test-station/operator/instrument identity where available;
- any repair, substitution, rework, debug intervention, or procedure deviation.

Please do not make silent design, BOM, assembly, repair, or test-procedure changes. Proposed changes should be returned as findings for review first.

## Commercial information requested

Please return:

1. quotation for fabrication + assembly for the smallest practical quantity;
2. minimum quantity;
3. functional-test engineering / NRE charge;
4. fixture/jig charge or assumption, if any;
5. operator/test labor charge or estimate;
6. expected production lead time;
7. expected test-engineering lead time;
8. any component procurement or through-hole assembly constraints;
9. steps that require explicit customer approval before proceeding.

## Required response summary

A concise response can use this format:

```text
Exact supplied package accepted without modification: YES / NO / NEEDS REVIEW
R1 DNP / R4 DNP / JP1 open state supported: YES / NO / NEEDS REVIEW
Cold raw measurements available: YES / NO / DETAILS
Staged current-limited power supported: YES / NO / DETAILS
Oscilloscope rail capture available: YES / NO / DETAILS
Bounded 0x9F-only first functional test supported: YES / NO / DETAILS
Raw SPI / JEDEC result available: YES / NO / DETAILS
Board/revision traceability in report: YES / NO / DETAILS
Silent substitution/repair avoided: YES / NO / DETAILS

DFM/DFA findings:
...

Quote / MOQ / NRE / fixture / labor:
...

Lead time:
...

Customer approvals required before production/test:
...
```

## Authority boundary

This inquiry requests a **quotation and engineering feasibility review only**. A provider response, quote, payment link, DFM report, or positive feasibility statement does not by itself authorize fabrication, assembly, power-on, functional test, or release. Those decisions are recorded separately against the exact campaign revision.
