# HS KiCad pin geometry challenge — native library pins versus converted schematic ports

**Executed 2026-10-24. Status:** real KiCad 9.0.8 and real `kicad-to-circuit-json@0.0.144` verification on Hardware Splicer's SPI-flash example, plus seven modified schematic variants. **Source-correlated pin locations only**, not native converter UUID provenance, junction/wire integrity, complete symbol graphics, PCB manufacturing, or physical repair.

## What this closes after PR #212

PR #212 verified the original 36 physical **symbol center positions** and the 79 *pin numbers*, but not actual pin coordinates. A visual representation could have every component at its correct center while rendering a pin in the wrong place or swapping two pins.

This trial reads independent positional evidence from the *native* `lib_symbols` definitions embedded in the original `.kicad_sch` source:

1. A physical KiCad source symbol is identified by its reference and native UUID. Its UUID is independently compared with the official KiCad-exported symbol `tstamps` through the earlier PR #212 gate.
2. Each embedded KiCad library symbol contains real `(pin ... (at x y angle) (number ...))` declarations, organized into sub-units.
3. The placed native symbol contains `(at x y rotation)`, optional `(mirror x|y)` and selected unit.
4. HS calculates an expected *native library pin* location after rotation/mirror and applies the previously independently calibrated KiCad-mm → converter-canvas coordinate transformation.
5. It verifies the converter's `source_port` and `schematic_port` identity relationships, exact pin-number sets and independent port-center coordinates, **for each pin**. Nothing is inferred from `schematic_trace` drawing coordinates.

On the existing SPI-flash reference design:

| Truth boundary | Executed result |
| --- | ---: |
| KiCad physical component instances | **36** |
| Original verified component centers | **36/36** |
| Native library physical pin positions | **79** |
| Converter port centers at predicted KiCad pin positions | **79/79** |
| Position mismatches | **0** |
| Maximum pin-center residual (converter coordinates) | **0.0** at stored precision |
| Authenticated original native KiCad UUID in converter output | **No** |
| Verified wire junctions/traces or complete rendered symbol shapes | **No** |
| Manufacturing/fabrication authority | **No** |

The source KiCad local library pin coordinates are in an axis where positive Y points upward, while sheet native schematic Y grows down. An instance rotation is applied to local pin coordinates first, then any `(mirror x|y)` across the global sheet axis, then absolute symbol placement. Native sheet pin coordinates map to converter positions through the anchored transformation established in PR #212:

```
converter_x = native_x_mm / 15 - 7
converter_y = -native_y_mm / 15 + 9.9
```

The transform was *not* refitted to pins or rotated variants. It is derived from 21 independent unique-component anchors from the earlier proof.

## Actual seven-variant validation against upstream converter

Rather than merely unit-test a mathematical formula, the regression suite creates altered copies of the **actual source schematic**, changes one legitimate KiCad component's orientation, exports the altered source through `kicad-cli sch export netlist` and runs the real upstream converter on the same altered `.kicad_sch`. The 36 components and all 79 physical pin centers then undergo the full audit again.

| Schematic variant | Actual source pin positions correlated | Outcome |
| --- | ---: | --- |
| Native source unchanged, zero-degree orientation | 79/79 | Pass |
| U1 rotated 90° | 79/79 | Pass |
| U1 rotated 180° | 79/79 | Pass |
| U1 rotated 270° | 79/79 | Pass |
| U1 mirror X, 0° | 79/79 | Pass |
| U1 mirror Y, 0° | 79/79 | Pass |
| U1 mirror X, 90° | 79/79 | Pass |
| U1 mirror Y, 90° | 79/79 | Pass |

These tests establish correct **pin-center transformation for one chosen native symbol** over the tested cardinal rotations and mirror combinations. They do not establish arbitrary symbol library compatibility, other unit selection behaviors, or multi-sheet visual integration. No physical pin probes, voltage measurements or boards were involved.

### Negative controls and meaning

- If one converter `schematic_port.center.x` shifts by 0.14 converter units, only **78/79** positions still match; the manipulated pin is recorded as `converter_pin_center_differs_from_native_kicad`, and the full parity flag becomes false.
- Swapping two port centers on the same converter component results in **77/79** matches, two explicit geometry discrepancies.
- Changing a native KiCad library pin coordinate without matching converter geometry is detected, even when symbol instance location remains unchanged.
- Scrambling unrelated converter document order cannot change the results because identities are matched through source IDs/pin numbers, not ordering.
- Changing one source UUID breaks the pre-existing official-export UUID check before any geometric decision.

**Persistent attack:** an attacker able to swap both an entire converter component record's center *and all its pin-center records* with those of an otherwise identical resistor could leave source-coordinate comparisons apparently correct while changing which converter-generated record ID is assigned to a native reference. The converter does **not emit native KiCad symbol UUIDs**. The audit therefore does **not** certify the provenance of the original converter record or allow an authoritative schematic geometry/electrical merge.

## Reproduce

Requires a genuine KiCad CLI installation and the existing upstream npm converter dependency:

```bash
pip install -e '.[dev]'
cd examples/integrations/kicad-circuit-json
npm install --no-audit --no-fund
npm run convert -- \
  ../../../hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_sch \
  /tmp/spi_converted.json
cd ../../..
python examples/integrations/kicad-circuit-json/audit_native_pin_geometry.py \
  --schematic hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_sch \
  --converter-json /tmp/spi_converted.json \
  --out /tmp/hs_kicad_pin_geometry_audit.json
pytest -q tests/test_kicad_native_pin_geometry_audit.py
```

The CLI invokes KiCad independently, creates a full pin-by-pin JSON audit and returns `all_pin_centers_correlated` plus explicit provenance/authority restrictions. Hashes and concise actual execution data were saved to `benchmarks/kicad_native_pin_geometry_20261024/real_kicad_pin_execution_receipt.json`.

**119 focused Python regression tests passed** across new pin-geometry checks and the existing native UUID/center proof, official hierarchical demos, Circuit JSON recovery, electrical interchange and repair-evidence suites. Two previously observed unrelated Python deprecation/OpenAPI warnings persisted. Full repository GitHub CI remains a separate release gate.

## What should be built next

1. **Native UUID propagation in converter output:** upstream or a source-preserving adapter must carry original KiCad symbol UUID plus sheet-instance UUID/path into individual converter source component and port records, not infer identity only by relative order or position.
2. Independently verify KiCad's complete schematic strokes, component orientation/mirror symbols, and the end-to-end geometry of `schematic_trace` edges/junctions with circuit net membership.
3. Only then construct a **separately gated visual overlay** between trusted KiCad electrical graph and external schematic drawing data. Keep authorization to manufacture tied to independent ERC/DRC, measured hardware validation and build checks, never to an image-coordinate match.

**Engineering verdict:** we have a repeatable digital verification of native pin centers on the SPI-flash source and seven orientation variants. Source-position evidence is materially stronger; upstream UUID identity and schematic wire geometry remain outstanding blockers. No claim of general-purpose repair capability or commercial product superiority is warranted from this alone.
