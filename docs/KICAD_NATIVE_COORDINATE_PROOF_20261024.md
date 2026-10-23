# KiCad native source-position and UUID correlation — 2026-10-24

**State:** Executed experiment using an actual KiCad 9.0.8 netlist export and `kicad-to-circuit-json@0.0.144` on the *same* checked-in SPI-flash schematic. Source-position and pin-number association **36/36**; upstream source-instance UUID provenance **still unauthenticated**; no visual/electrical merge or fabrication approval.

## Previous limit and what's new

PR #211 matched only **21 of 36** KiCad component identities to the converter's schematic records, on a uniquely occurring `(lib_id, value)` + exact pin-number set. Fifteen duplicates (10 kΩ / 0 Ω resistors, identical capacitors, GND test points) were legitimately refused.

This PR uses **native .kicad_sch symbol instance coordinates and UUIDs**, verified against the **same original KiCad schematic's independent official netlist export**, as a separate origin of evidence. It derives the converter's coordinate frame solely from the 21 uniquely identified anchors, checks every anchor agrees with the resulting transformation, and then tests previously ambiguous components against the independently sourced symbol positions.

This is *not* a guarantee that the converter carried UUIDs; it does not. The inferred mapping remains only **position-correlated provenance** until the upstream converter independently emits the corresponding UUID+sheet instance path.

## Actual results (SPI flash adapter v1)

| Test item | Result |
| --- | ---: |
| Official KiCad exported physical components | **36** |
| External converter `source_component` records | **40**, including 4 `power:PWR_FLAG` symbols |
| Independently unique library/value + pin-number anchors | **21** |
| Source pin numbers covered by those 21 anchors | **52** |
| Further duplicate-valued components with transformed source positions aligned | **15** |
| Total KiCad references with coordinate-correlated converter schematic component + exact pin-set | **36 / 36** |
| Source numbered pin memberships on those 36 components | **79** |
| Largest observed symbol-center residual in converter units | **0.0** after round-off |
| Verified native KiCad symbol UUID vs KiCad netlist `tstamps` | All 36 |
| Upstream converter records containing original KiCad symbol UUID | **0** |
| Independently verified schematic symbol shapes and pin *positions* | **No** |
| Automatically merged converter visual + KiCad electrical circuit | **No** |
| Authorized PCB fabrication / repair | **No** |

The native→converter source coordinate transform was measured, not assumed:

```
converter_x = native_x_mm / 15 - 7
converter_y = -native_y_mm / 15 + 9.9
```

All 21 distinct anchors agreed with this transform within a strict absolute tolerance of `1e-6` converter units. Of those anchors, two extreme native positions establish the per-axis linear transform and the others act as consistency checks. The 15 originally ambiguous parts had exactly one matching geometry center at their predicted source coordinates within the same tolerance, with no reused component IDs. Their complete source pin-number sets and schematic-port parent mappings also matched.

The 15 additional correlated parts were `C1`, `C3`, `C4`, `C5`, `C6`, `R1`, `R2`, `R3`, `R4`, `R5`, `R6`, `R7`, `TP4`, `TP17`, `TP18`. None were assigned based on the external document order.

**Important qualification:** all 79 verified pin numbers are attached to the correct candidate component records. The *geometric positions of those pins* and the displayed symbol shapes have **not** been independently checked against native KiCad symbol library geometry. This experiment certifies **component centers and pin-number memberships** only.

## Proof boundaries and adversarial testing

The new `src/hardware_splicer/integrations/kicad_native_coordinate_proof.py`:
- requires **both** native `.kicad_sch` and actual official KiCad S-expression export,
- rejects a source symbol UUID that disagrees with the exported symbol instance `tstamps`,
- requires 4+ previously uniquely validated component anchors and consistent translation/scaling with mirrored Y orientation; no single-anchor guess,
- checks exact component type/value, all source/visual port links and source pin-number set, finite coordinates and unique candidate geometry assignment,
- refuses tampered anchor geometry or a displaced ambiguous resistor; such tampering cannot be promoted into a full-correspondence claim,
- remains strictly **single-sheet**, inherited from PR #211's geometry identity audit, and explicitly refuses automatic merged visual/electrical artifact generation.

**Deliberate unsolved attack:** when the centers of the converter records for two *otherwise identical* 10 kΩ resistors are exchanged, the system still finds 36 plausible position-to-source correspondences, but the converter record IDs assigned to `R2` and `R3` swap. With no original UUID in the converter record, there is no independent witness to disprove that swap. The negative test confirms this unavoidable ambiguity and asserts `converter_record_provenance_authenticated=false` and `visual_electrical_geometry_merge_allowed=false` even on the 36/36 result.

Similarly, **matching the source center** is not proof that the converter reproduced the correct pin positions, symbol orientation, mirror settings, linework, dimensions, or junction/trace topology. None of those unresolved geometric properties has been marked verified.

## Reproduce against genuine tooling

```bash
pip install -e '.[dev]'
sudo apt-get install kicad
cd examples/integrations/kicad-circuit-json
npm install --no-audit --no-fund
npm run convert -- \
  ../../../hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_sch \
  /tmp/spi_converter.json
cd ../../..
python examples/integrations/kicad-circuit-json/prove_native_coordinates.py \
  --schematic hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_sch \
  --converter-json /tmp/spi_converter.json \
  --out /tmp/hs_native_geometry_proof.json

pytest -q tests/test_kicad_native_coordinate_proof.py
```

The CLI invokes official `kicad-cli sch export netlist --format kicadsexpr` and saves the complete component-by-component sidecar evidence without changing the actual converter records or HS's electrical graph. Executed condensed receipt with source and converter hashes:
`benchmarks/kicad_native_coordinate_20261024/actual_kicad_converter_position_execution_receipt.json`.

**106 focused Python tests passed** with KiCad 9.0.8, the genuine upstream converter and the official KiCad demo package installed. The regression suite included previous hierarchical source identity, interchange and repair evidence checks. Full GitHub CI and comprehensive other-layout tests remain separate release gates.

## Next real gate

1. Add *upstream converter-carried* native symbol UUID and sheet-instance metadata (prefer a validated contribution upstream rather than inventing fragile identifiers in HS). This is the only reliable way to independently attest identity of interchangeable same-value components.
2. Compare each schematic pin's *actual coordinate* and symbol orientation/size against native KiCad library + instance geometry under the verified transform. Then test deliberate pin swaps, flips, and rotations.
3. Only after authenticated UUIDs, symbol instances, pin positions and net references all agree, permit a separately gated preview overlay. Such a preview would still not imply safe fabrication, electrical performance, or repaired hardware.

**Verdict:** all components in this **one single-sheet design** have strong native-source spatial correlations. This removes the original 15 unresolved position mappings for display correlation, but not the upstream UUID provenance or pin-geometry verification blocker.
