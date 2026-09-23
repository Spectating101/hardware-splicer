# ProofPod v0 — Product Factory Run PF-001

ProofPod v0 is the first attempt to use Hardware Splicer as a **commercial hardware product factory**, not merely as a project being evaluated.

The hypothesis is narrow: professional embedded tools often sell for hundreds of dollars even when the underlying low-speed digital hardware is modest. The value is in protection, deterministic behavior, software workflow, support and confidence. ProofPod tests whether Hardware Splicer can turn those same value layers into a lower-cost product without pretending it can beat $15 hobby bridges on raw protocol access.

## Product wedge

ProofPod v0 is a USB-C **SPI/I2C validation pod** with selectable 1.8 V / 3.3 V low-current target power, current/rail telemetry, default-disabled target signals, default-off target power, read-only defaults, a physical write-arm input, and revision/firmware/power/transaction evidence receipts.

It is intentionally **not** a logic analyzer, oscilloscope, SWD/JTAG product, galvanically isolated instrument or precision power analyzer in v0.

## Commercial design constraints

- board-only target MSRP: **US$79**
- kit target MSRP: **US$99**
- board landed COGS ceiling at 100 units: **US$20**
- kit landed COGS ceiling at 100 units: **US$30**
- current preliminary board budget: **US$18.65**
- target gross margin at the design ceiling: **>=65%**

These are design constraints, not supplier quotes or demand validation.

## Product Factory flow

PF-001 uses the sequence:

`DISCOVER -> SELECT -> SPECIFY -> DESIGN_SCHEMATIC -> VERIFY_SCHEMATIC -> DESIGN_PCB -> VERIFY_PCB -> SOURCE -> BUILD -> PROVE -> BENCHMARK -> SELL -> LEARN`

The canonical state is `experiments/product_factory/run-001-proofpod.json`.

The first selection gate is implemented by `experiments/commercial_arbitrage/evaluate.py`; it rejects weak margins, cherry-picked expensive competitors, high calibration burden and products with little Hardware-Splicer-native leverage.

## First engineering correction

The initial concept used a generic load switch while also claiming a <=250 mA target-power limit. That architecture did not actually enforce the contract.

PF-001 corrected the design before PCB work to **TPS2553DBVR** with a 133 kOhm ILIM resistor. The design manifest records approximately 201.5 mA nominal and 233.9 mA datasheet maximum before external-resistor tolerance, plus reverse-voltage protection for external-target mode.

## Schematic gate

The current branch contains:

- `architecture_manifest.json` — exact selected architecture and unresolved blockers;
- `HardwareSplicer.kicad_sym` — reviewable local symbols for TXU0304 and TPS2553;
- `generate_schematic.py` — deterministic KiCad schematic generator;
- `verify_schematic.py` — explicit required-topology + native KiCad ERC gate;
- `.github/workflows/proofpod-factory.yml` — CI execution and evidence artifact.

The gate requires the target-current path, default-off controls, SPI OE, physical write-arm input, selected rail topology and component identities to match the contract, then requires **zero ERC violations**.

## Current truth state

**SCHEMATIC GATE PENDING CI.**

There is no verified schematic receipt yet, no PCB, no fabrication package, no physical validation, no demand validation and no evidence of commercial superiority.

Even a clean schematic gate authorizes only continued design work. PCB routing remains blocked until the unresolved USB-C connector, crystal/loading, ESD parts, frozen source documents and independent EE review are closed.
