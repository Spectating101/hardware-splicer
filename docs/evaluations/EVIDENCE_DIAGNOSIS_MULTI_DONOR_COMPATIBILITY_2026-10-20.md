# Hardware Splicer: repair differential and multi-donor compatibility

Date: 2026-10-20. Software-only investigation on Optiplex.
This is a follow-on to the explicit mission contracts in PR #150.

## Repair: one broken LS2208 scanner

Primary model-family reference: Zebra LS2208 Product Reference Guide:
https://www.zebra.com/content/dam/support-dam/en/documentation/unrestricted/guide/product/ls2208-prg-en.pdf

Zebra documents different replaceable host-interface cable arrangements,
including USB and RS-232. A Ruten seller describes one LS2208 as having a
cut cable. That description alone cannot identify its host cable variant,
pinout, internal state, or sole cause of failure.

The new differential analysis ranks four *unverified* explanations:
1. Severed cable or damaged host connector;
2. Wrong host/interface cable or mismatch;
3. Internal electronics or optical scanner fault;
4. Configuration or decode settings incompatibility.

A concrete seller-reported break is prioritized as a discriminating
investigation question over generic words such as "scanner" and
"barcode". This is not a numerical probability or confirmed diagnosis.

The repair investigation includes the model family reference, matched
reported symptoms, each competing fault hypothesis, next evidence
needed to distinguish hypotheses, and explicitly withheld authority.
No pinout, replacement wiring, powered diagnostic action or completed
repair was invented. Unknown models without a dedicated profile stay
unresolved instead of borrowing LS2208-specific knowledge.

## New product: four heterogeneous damaged donor listings

Target: tabletop barcode-inspection and object-indexing station.
No physical machine or donor assembly has been observed.

| Source and proposed module | Product function | Crucial missing evidence |
| --- | --- | --- |
| LS2208 scanner with severed cable | barcode decoding | operating scanner, exact host cable and signal/power interface |
| Epson LQ-680 faulty printer without printhead | controlled indexing mechanism | motor/mechanics presence, geometry, winding/driver, travel limits |
| QNAP TS-219P II bare board without PSU | local processing | safe power supply, host interfaces, OS support, independent boot |
| Apple mouse with faulty optical tracker | ordinary input buttons | actual contact wiring; NOT a validated safety stop |

The input component hypotheses bind to exact marketplace source IDs and
explicit target function tags. No product-goal keyword matching is used.
The Apple mouse only partially satisfies the operator input/stop role:
its buttons cannot be accepted as a safety-rated stop mechanism.

The system reports proposed connections between the scanner and
computer, printer mechanism and computer, and mouse buttons and computer.
All three are BLOCKED because signal protocols, connectors and voltages
are unverified. An asserted paper match also remains blocked until
separate verified physical and electrical evidence exists.

Outputs:
- REPAIR_INVESTIGATION.json now includes differential_diagnosis,
  family documentation, ranked questions, and root_cause_verified=false.
- MULTI_DONOR_COMPATIBILITY.json includes component candidate identities,
  direct/partial function coverage, interface conflicts and missing
  facts, and all_proposed_links_physically_blocked=true.
- ENGINEERING_MISSION_EVALUATION.json continues to report mission failure.
  A carrier KiCad compile is a different, lower-level result.

The exact model-family manual does not validate the particular used
device. Seller records do not establish that missing parts are present,
the device works, or the user has acquired it. The source quality
category in an input is not an authenticated document check and never
elevates a candidate to an independently measured module.

## Next physical proof requirements

- Repair: actual specimen ID, photos and cable model, independently
  observed baseline failure, inspected cable/interface evidence,
  documented model-compatible procedure, operator repair and scan test.
- Splicing: actual source-specific harvested modules, interface
  measurements, mechanical fitting and motor/driver selection,
  firmware/control tests, safety-rated stop solution, and observed
  functional integration.

Neither software path grants electrical, fabrication, motion, repair
or power-on authorization. No physical acquisition or actuation occurred.

Regression scope: 96 passed, 1 skipped, 1 warning including prior
mission contracts and commerce/salvage tests.
