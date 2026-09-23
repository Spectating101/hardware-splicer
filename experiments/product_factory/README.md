# Hardware Splicer Product Factory

The Product Factory is the commercial self-use lane of Hardware Splicer.

Its purpose is not to claim that every expensive product can be cheaply cloned. Its purpose is to repeatedly test whether Hardware Splicer can turn a sourced market gap into a verified, manufacturable product while preserving the same evidence and authority boundaries used elsewhere in HS.

## Canonical stage model

`DISCOVER -> SELECT -> SPECIFY -> DESIGN_SCHEMATIC -> VERIFY_SCHEMATIC -> DESIGN_PCB -> VERIFY_PCB -> SOURCE -> BUILD -> PROVE -> BENCHMARK -> SELL -> LEARN`

Each run is a machine-readable record under `experiments/product_factory/`.

## Gate semantics

- **DISCOVER**: source current market anchors and customer/job evidence.
- **SELECT**: prove only that the opportunity deserves engineering time.
- **SPECIFY**: freeze price, COGS, safety, scope and non-goal contracts.
- **DESIGN_SCHEMATIC / VERIFY_SCHEMATIC**: exact parts, pin/net topology and native ERC.
- **DESIGN_PCB / VERIFY_PCB**: layout, parity, DRC and manufacturing artifacts.
- **SOURCE**: replace budget assumptions with supplier/fabricator quotes and substitution risk.
- **BUILD**: requires explicit human fabrication authority.
- **PROVE**: bind real physical evidence to the exact revision.
- **BENCHMARK**: compare measured workflow/performance against named incumbents.
- **SELL**: requires a human commercial decision and truthful product claims.
- **LEARN**: preserve every discovered defect, failed assumption, cost miss and market result.

A stage PASS grants authority only to enter the next engineering stage. It never implies physical correctness, demand, revenue or superiority unless that evidence exists.

## Required economics

Every run must freeze at minimum:

- target MSRP;
- landed COGS ceiling at a stated quantity;
- minimum gross-margin floor;
- preliminary BOM/assembly budget;
- at least one low-cost market floor;
- at least two relevant professional/commercial anchors when the thesis is price arbitrage.

The design must fail closed if economics degrade below the frozen floor before physical build.

## Required evidence

A successful run should eventually preserve:

`market sources -> product contract -> exact design revision -> verification receipts -> supplier quote -> build identity -> physical evidence -> benchmark -> commercial result`

This chain is itself a Hardware Splicer benchmark.

## PF-001

`PF-001 / proofpod-v0` is the first run.

It tests a protected SPI/I2C validation pod positioned between cheap bare protocol bridges and professional embedded host/programmer tools.

The run is intentionally allowed to fail. A useful failure that exposes a design, sourcing or market flaw before production is positive evidence about the Product Factory workflow.
