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

## Refinery intake

Refinery can now hand a screened market hypothesis to Product Factory through `hardware_splicer.product_factory_seed.v1`.

The importer is:

`experiments/product_factory/import_refinery_seed.py`

A valid seed may open **design work only**. The importer rechecks economics and refuses any seed that attempts to grant fabrication or physical authority. The generated run starts at `READY_FOR_HS_PRODUCT_CONTRACT`; Hardware Splicer must still establish its own specification, schematic, PCB, sourcing, physical proof and benchmark.

This keeps the cross-system contract explicit:

`Refinery reviewed market -> Spectator commercial enrichment -> Refinery gate -> HS Product Factory -> Gauntlet conversion -> Refinery learning`


## Supply substrates

Product Factory is not restricted to clean-sheet assembly from newly purchased parts.

Supported supply modes now include:

- `NEW_BUILD`
- `DONOR_RETROFIT`
- `MODULE_REUSE`
- `COMPONENT_HARVEST`
- `HYBRID`

The economics gate prices donor acquisition, shipping, inspection labor, usable yield, reject disposal/recovery, rework, new material, final QA and warranty reserve into **effective COGS per sellable unit**. Donor identity, revision capture, variant-specific acceptance, observed supply depth and hazard boundaries fail closed.

The preferred reuse pattern is normally whole-device/module transformation before individual component harvesting because splicing can preserve working compute, enclosure, interfaces, mechanics and certified external subsystems without paying desolder/test labor on every component.

The first real-market probe is `donor_probes/benchnode_v0_market_probe.json`: an off-lease thin-client donor plus a new HS-designed low-voltage I/O/protection sidecar. Its paper economics are attractive, but its supply route remains HOLD until exact-model bulk depth and measured donor yield exist.


## Competitive role

Product Factory is also an empirical test of whether Hardware Splicer belongs at a higher layer than individual EDA operations.

The hypothesis is:

```text
requirement
  -> choose NEW_BUILD / MODIFY / MODULE_REUSE / DONOR_RETROFIT / HYBRID
  -> execute engineering with HS and/or specialist tools
  -> preserve exact artifact/revision identity
  -> verify
  -> obtain physical evidence
  -> bind economic outcome
```

The strategic consequence, if physically demonstrated, is that schematic generation, PCB layout, simulation and design review can become **operators underneath HS** rather than capabilities HS must win independently against every specialist vendor.

See `docs/COMPETITIVE_CATEGORY_SHIFT_2026Q3.md`.

This is not yet a proven moat. The current Product Factory code and CI establish workflow/gate existence only. Generality requires multiple materially different physical transformations, and commercial defensibility requires real cost/yield/customer outcomes.
