# Platform Artifact Units v1

**Policy id:** `platform-artifact-units-v1`  
**Purpose:** make platform-reuse accounting stable enough that a derivative cannot appear more reusable merely because files were split, renamed, or generated differently.

## Rule

An artifact unit is a **stable engineering obligation or contract**, not a file.

The baseline inventory must be frozen before derivative implementation starts. A later derivative may mark each baseline unit `inherited` or `changed`; genuinely new obligations are `new`. File count, generated-line count, repository layout, and documentation page count do not create additional units.

## Unit classes

Use these classes unless the baseline records a justified extension before derivative work begins:

| Class | Unit boundary |
|---|---|
| `hardware_bom` | one functionally distinct procured/assembled hardware role whose identity or electrical contract can change independently |
| `electrical_interface` | one independently testable electrical/interface contract |
| `firmware_capability` | one operator-visible or hardware-facing firmware capability with its own acceptance condition |
| `software_interface` | one stable external/API/configuration contract |
| `mechanical_contract` | one independently changeable mount/enclosure/geometry contract |
| `verification_protocol` | one independently executable verification obligation |
| `data_model_pipeline` | one frozen data/model/training/deployment obligation whose validity can change independently |
| `operator_workflow` | one independently testable operator task/handoff contract |

## Anti-gaming constraints

1. **Do not use source files as units.** Ten files implementing one camera-capture capability are one firmware-capability unit if they change and validate together.
2. **Do not split a unit after seeing derivative results.** Baseline unit ids and class assignment are frozen before derivative implementation.
3. **Do not merge changed units after seeing derivative results.** If two baseline obligations were independently changeable and separately validated, they remain separate units.
4. **Generated duplicates do not multiply reuse.** Mirrored JSON, rendered documentation, generated code and packaged copies inherit the unit id of the engineering obligation they represent.
5. **A unit is inherited only if its defining contract and required evidence remain valid.** Reusing implementation text is insufficient.
6. **Unknown dependency impact is not inherited.** It is blocked until dependency coverage is resolved.
7. **New market-facing behavior is not automatically a new core unit.** It is new only when it introduces a distinct engineering obligation rather than a parameter/configuration of an existing frozen contract.

## Hash boundary

Before derivative work begins, persist:

- policy id;
- ordered baseline unit inventory;
- each unit id/class and defining contract reference;
- artifact/evidence hashes where available;
- SHA-256 of the normalized baseline inventory.

`PLATFORM_DERIVATIVE_EVIDENCE.template.json` stores that hash as `baseline_inventory_hash`.

## Reuse interpretation

`engineering_reuse_ratio = inherited units / total candidate units`

The evaluator also reports class-level reuse and a class-balanced ratio. The precommitted headline gate remains the total unit ratio, while class-level results are retained so a derivative cannot hide a complete rewrite of one important class behind many inherited units elsewhere.

Engineering-hour compression remains a separate metric. High artifact reuse with high engineering effort is **not** successful arbitrage.

## Policy changes

A future accounting policy may supersede this one, but it must receive a new policy id. Existing experiments are never rescored under a later policy merely because the new policy produces a more favorable result.
