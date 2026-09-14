# Derived Virtual Lab v1 — passing software-only milestone

Date: 2026-09-14

Status: **PASS as derived/surrogate software evidence only**.

This record freezes the first complete Hardware Splicer Derived Virtual Lab v1 run. It does
not claim manufacturer-model validation, measured bench evidence, physical correctness,
fabrication readiness, power-on readiness, or physical authority.

## Frozen execution identity

- Repository: `Spectating101/hardware-splicer`
- PR: `#94` (`Add Derived Virtual Lab v1 benchmark`)
- Experiment branch: `experiment/derived-virtual-lab-v1-20260914`
- Experiment head: `2a60427f0167d8820f1317e950a9bd6a4277c798`
- GitHub Actions workflow: `SPI Derived Virtual Lab`
- Workflow run: `34829229335`
- Artifact ID: `10340974166`
- Artifact name: `spi-derived-virtual-lab-v1`
- Artifact size: `87,795` bytes
- Artifact ZIP digest: `sha256:88cc364e5bee388c0fc53c9aa6b8e2d9d4d93616a11ae9223e400ecdfbbdbc04`

Every step in the dedicated workflow passed:

1. focused Derived Virtual Lab tests;
2. frozen 512-case benchmark execution;
3. per-case result export;
4. independent serialized-data gold/evaluator audit;
5. Icarus Verilog read-only protocol cross-check;
6. analytical-RC versus ngspice cross-check; and
7. artifact publication.

## 512-case benchmark result

The frozen Cartesian corpus contains:

- 8 fault profiles;
- 4 SPI clock points;
- 4 derived current-load points; and
- 4 DUT-rail points.

Total: **512 cases**.

Observed outcome matrix:

| Independent/frozen class | Predicted safe | Predicted blocked | Predicted unsafe |
| --- | ---: | ---: | ---: |
| Safe | 24 | 0 | 0 |
| Blocked | 0 | 24 | 0 |
| Unsafe | 0 | 0 | 464 |

Aggregate results:

- unsafe false negatives: **0**;
- safe false rejections: **0**;
- blocked misclassifications: **0**;
- authority-boundary violations: **0**;
- repair-eligible cases: **168**;
- successful scripted repairs: **168**;
- scripted repair success rate: **1.0**;
- corpus digest: `sha256:3c18afb3112060b415ce4356a122dee08d3c7859332c1eee1e5d596f7d2019d3`.

Scripted repair is a deterministic control and is **not** evidence of AI competence.

## Independent serialized-data audit

A separate auditor that does not import `spi_derived_virtual_lab` recomputed the gold labels
from the serialized cases and compared them with the frozen labels and evaluator outputs.

Result: `passed_independent_derived_audit`.

Checks passed:

- exact 512-case count;
- unique case IDs;
- exact result coverage;
- all frozen labels match the independent gold implementation;
- all evaluator predictions match the independent gold implementation;
- aggregate matrix matches the independent recomputation;
- benchmark report claims pass; and
- benchmark report keeps authority closed.

Mismatch counts:

- frozen-label mismatches: **0**;
- evaluator mismatches: **0**;
- missing results: **0**;
- extra results: **0**.

Bound input hashes:

- benchmark report: `sha256:4273fc36f8b56b89b8c61f0cbfad9ca498b14451580ec208d32637dee6ee0ac2`;
- corpus: `sha256:9a41bf1f0589cc2cb59e709dace62b035947a25d57ef6dcb688c88732233445d`;
- per-case results: `sha256:38e95e8cce4c47e32f1cd1be5c42ad7e764c6c169aee0b1e71b67899237284b4`.

## Read-only Verilog reference cross-check

The derived Python protocol oracle was independently cross-checked with the bounded Verilog
reference model using Icarus Verilog.

Result: `passed_derived_reference`.

- compile exit: `0`;
- simulation exit: `0`;
- JEDEC-ID check: **PASS** (`EF 60 18`);
- mutating-command rejection check: **PASS**;
- model SHA-256: `sha256:76c03a6e72d2f0e80316ee4a221e7d489627b36ce286dc5e59fdc6491cc19367`;
- testbench SHA-256: `sha256:543cc3698796a821f3f9701ba633f717066102b9d8af6d868895b6a77c70e16e`.

This reference model is not the Winbond vendor model and receives no vendor-model campaign
credit.

## RC / ngspice cross-check

A 36-case analytical RC grid was generated from:

- rail: `1.773`, `1.800`, `1.827` V;
- source resistance: `50` ohm surrogate assumption;
- series resistance: `0`, `22`, `47` ohm;
- load capacitance: `10`, `25`, `50`, `100` pF.

Four selected corners were independently executed in ngspice. All passed the preregistered
5% relative-error ceiling:

| Case | Analytical 10–90% rise | ngspice 10–90% rise | Relative error |
| --- | ---: | ---: | ---: |
| 1.800 V, 22 ohm, 25 pF | 3.955004 ns | 3.955000 ns | 0.000107% |
| 1.773 V, 0 ohm, 10 pF | 1.098612 ns | 1.098630 ns | 0.001612% |
| 1.827 V, 47 ohm, 100 pF | 21.313078 ns | 21.313100 ns | 0.000101% |
| 1.800 V, 47 ohm, 50 pF | 10.656539 ns | 10.656500 ns | 0.000368% |

This proves consistency between the encoded first-order RC arithmetic and the selected ngspice
networks. It does **not** establish real TXU0304/W25Q128JW signal integrity and is not IBIS.

## Source-bound input manifest

The experiment artifact includes a manifest binding the derived lab to the exact canonical
inputs inherited from PR #93.

Manifest SHA-256:

`sha256:0d1428b1c21e0d9ad879cfa0acd2e2f23f5704f6c4ad188b1a5a4aa718a39577`

Canonical-input hashes:

- virtual target: `sha256:6f3fd638024e9e6c7dd547923357ead41e1b9c2c669a11a5bcfa86c19afb1b3f`;
- timing inputs: `sha256:0ba2c09452f8ffe91e25fada55bff3a8de69ba680a4d4fa5d788b09836d6308a`;
- power inputs: `sha256:d8e4be1a83c4d8cab1c1305602fb17fa1122dd3bca156f0a94a1cbb027414f42`.

Selected inherited terms include:

- host logic high: `3.3 V`;
- DUT supply range: `1.7–1.95 V`;
- DUT pin absolute-maximum rule: `VCC + 0.4 V`;
- TXU A→B maximum propagation term: `19 ns`;
- TXU B→A maximum propagation term: `15 ns`;
- W25Q clock-low-to-output-valid term: `6 ns`;
- TLV75518PDBVR regulator capacity: `500 mA`;
- regulator output envelope: `1.773–1.827 V`.

## Claim boundary

This milestone establishes that the frozen **derived** Hardware Splicer software-verification
stack can generate, classify, independently audit, and deterministically repair a broad SPI
adapter fault/corner corpus while preserving the declared authority boundary. It also shows
agreement between two protocol-reference implementations and between analytical RC arithmetic
and selected ngspice transients.

It does **not** establish:

- manufacturer IBIS or manufacturer Verilog model behavior;
- source authenticity beyond the upstream source records;
- independent EE correctness of every source-derived assumption;
- physical DUT identity;
- real programmer electrical behavior;
- real package/interconnect parasitics;
- schematic/ERC/PCB/DRC closure;
- bench measurements;
- fabrication or power-on readiness;
- physical correctness; or
- physical authority.

Astra was not used for this milestone.
