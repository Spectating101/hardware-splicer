# ProofPod v0 — commercial design pilot

ProofPod v0 is the first attempt to use Hardware Splicer as a **commercial hardware design engine**, not merely as a project being evaluated.

The commercial hypothesis is narrow: professional embedded tools often sell for hundreds of dollars even when the underlying low-speed digital hardware is modest. The value is in protection, deterministic behavior, software workflow, support and confidence. ProofPod tests whether Hardware Splicer can turn those same value layers into a lower-cost product without competing with $15 hobby breakouts on raw component access.

## Product wedge

ProofPod v0 is a USB-C **SPI/I2C validation pod** with:

- host-controlled SPI and I2C transactions;
- selectable 1.8 V / 3.3 V low-current target power;
- external target-VREF mode for already-powered targets;
- current and rail telemetry before a transaction;
- target signals disabled by default;
- target power off by default;
- read-only behavior by default;
- a physical write-arm requirement for destructive SPI operations;
- revision/firmware/power/transaction evidence receipts.

It is intentionally **not** a logic analyzer, oscilloscope, SWD/JTAG probe or precision power analyzer in v0.

## Market boundary

Observed 2026 reference points are stored in `experiments/commercial_arbitrage/market_scan_2026-09-23.json`.

The useful price corridor is not the bottom of the market. A bare Adafruit FT232H breakout is about $15 and Bus Pirate 5 is roughly EUR59-EUR89. The professional reference set is materially higher: DediProg SF100 at $275 and Total Phase Aardvark at $375.

The initial commercial target is therefore:

- **$79 board-only**;
- **$99 kit** with enclosure/cable/target breakout;
- board-only landed COGS ceiling **$20 at 100 units**;
- kit landed COGS ceiling **$30 at 100 units**;
- target gross margin >= **65%**.

Those numbers are design constraints, not supplier quotes.

## Why Hardware Splicer should be useful here

The differentiator is native to HS:

`exact design revision -> deterministic checks -> protected physical action -> transaction evidence -> explicit authority`

A generic protocol bridge can send bytes. ProofPod should additionally be able to prove which hardware/firmware/power state sent them and whether a destructive operation was physically authorized.

## Current truth state

This branch is **CONCEPT_CONTRACT only**.

There is no completed schematic, PCB, fabrication package or physical validation yet. Commercial superiority is a hypothesis to test, not a current claim.

The next gate is exact component/symbol selection followed by generated KiCad schematic + ERC/topology checks. No routing or fabrication should begin before that gate passes.
