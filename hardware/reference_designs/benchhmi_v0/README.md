# BenchHMI v0 — PF-002

PF-002 is the first Taiwan-local donor/remanufacture Product Factory run.

Instead of creating a panel PC from a new display, new computer, new enclosure and new power system, the run asks whether Hardware Splicer can preserve the high-integration value already present in a retired POS terminal and add only the missing modern test/automation capability.

## Exact donor

Flytech POS462 with the B91 motherboard family only.

The B91 manual documents a 12.1-inch resistive touch display for POS462, SATA storage, up to 4 GB DDR2, 10/100/1000 Ethernet, four rear powered COM ports, six external USB ports and Linux support.

PF-002 does not treat B81 and B91 as interchangeable.

## Product hypothesis

POS462/B91 donor + refreshed storage + external BenchIO sidecar + frozen Linux console image + finished-unit QA receipt.

The intended result is a bench/lab automation console, not a certified industrial HMI.

## Why the sidecar stays external

The donor's internal ATX/mains architecture is valuable precisely because it is already integrated. PF-002 does not redesign or modify it. Any donor requiring mains-side repair is rejected.

The new BenchIO board is USB-connected and low-voltage/SELV only. This lets HS test the splice thesis without turning a donor-remanufacture experiment into a mains-safety redesign.

## Current economics

Screening model, not production evidence:

- donor target: NT$1,000;
- target MSRP: NT$8,990;
- modeled effective COGS: about NT$3,642;
- modeled gross margin: about 59.5%;
- all-new reference COGS hypothesis: NT$7,500;
- first lot: 20 units.

The donor economics evaluator still fails closed on scale because qualified lot depth and measured yield are not established. The product-facing state is **EVIDENCE_PENDING_SUPPLY_AND_YIELD**, not a failure state.

## Next evidence

1. Inspect/acquire a bounded POS462 sample without authorizing production.
2. Confirm exact B91 identity.
3. Test cold boot, LCD/touch, Ethernet, USB and all required COM ports.
4. Install the candidate lightweight Linux image and verify touch/serial behavior.
5. Record actual inspection time and pass/fail yield.
6. Find an exact-model lot/source large enough to support the intended first run.
7. Only then open BenchIO sidecar schematic work.

A successful PF-002 should demonstrate more than cheap assembly: it should show Hardware Splicer can identify, preserve and verify valuable subsystems in existing hardware while adding a new custom capability layer.


## Status language

PF-002 uses progressive states for ordinary sequencing:

- `AWAITING_*` — an external/input dependency is not present yet;
- `EVIDENCE_PENDING_*` — the hypothesis remains active while evidence is gathered;
- `READY_*` — the next engineering action may start;
- `QUEUED_AFTER_*` — a later lifecycle stage is intentionally downstream;
- `ACTIVE_*` — work is currently open.

`BLOCKED_*` is reserved for a real defect, contradictory evidence, failed verification, or safety stop. A healthy future stage is not presented as broken merely because its prerequisite has not happened yet.
