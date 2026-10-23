# Hardware Splicer — KiCad converter schematic geometry identity challenge

**Execution:** 2026-10-24. **Status:** real upstream converter + official KiCad 9.0.8 experiment, partial **metadata identity correlation only**, no verified symbol UUID/coordinate mapping and **no geometry merge**.

## Why this challenge exists

The preceding PRs #209–#210 showed that HS can reconstitute correct electrical connectivity from **official KiCad source netlist exports**, including complex hierarchical schematics. The external open-source `kicad-to-circuit-json@0.0.144` converter supplies schematic visual coordinates, but not native KiCad component reference designators or symbol UUIDs and does not emit `source_trace` electrical connectivity for our SPI-flash example. Those are serious limits to merging its visual design with KiCad's authoritative nets.

We tested whether the available converter metadata can at least identify individual schematic *visual components* without relying on drawing order, estimated position or name guessing.

## Actual experiment

For the unchanged `hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_sch`:
1. Ran the **real `kicad-cli 9.0.8`** netlist exporter, preserving exported reference, library symbol identity (`libsource.lib:libsource.part`), displayed `value`, and original connected pin numbers.
2. Ran the actual `kicad-to-circuit-json@0.0.144` converter on the **same .kicad_sch**. The upstream source component fields are `name` (KiCad library symbol) and `manufacturer_part_number` (in this converter output, this often holds the **displayed value**, not necessarily an authenticated manufacturer part number).
3. Matched a converter visual symbol to an exported reference **only if** `(symbol library ID, displayed value)` appears **exactly once** in BOTH projects; the external and KiCad source pin-number **sets are exactly equal**; one valid visual component exists; all external source ports have consistent and uniquely linked schematic ports and pin numbers; and visual geometry has finite coordinates.
4. **Refused** ambiguous repeated resistors/capacitors/test points and extra converter-only symbols. No positional matching, component ordering or synthetic net-to-pin wiring.

| Audited property | Actual count |
| --- | ---: |
| Official KiCad exported physical components | **36** |
| Third-party converter `source_component` records | **40** |
| Correlated one-to-one metadata identities | **21 of 36** |
| Corresponding numbered physical electrical pins | **52** |
| Ambiguous KiCad component identities, withheld | **15** |
| Extra upstream `power:PWR_FLAG` symbols | **4**, not promoted into the KiCad BOM |
| Upstream `schematic_trace` geometry records | **87** |
| Upstream verified electrical `source_trace` records | **0** |
| Authenticated KiCad UUID ↔ converter drawing coordinates | **0** |
| Automatically merged visual geometry | **0** |
| Independently verified physical repairs/manufacture | **0** |

**21 metadata-correlated visual identities are not 21 verified geometric placements.** There is no direct per-symbol UUID, sheet scope or source-position attestation in converter records, and therefore all 21 remain merely candidates in a sidecar audit.

### Explicitly unresolved elements

The 15 source references withheld from identity assignment are:
`C1`, `C3`, `C4`, `C5`, `C6`, `R1`, `R2`, `R3`, `R4`, `R5`, `R6`, `R7`, `TP4`, `TP17`, `TP18`.

These are genuine multiple instances of the same component-library ID and displayed value. Their approximate positions are insufficient electrical identity evidence.

The four external `power:PWR_FLAG` symbols also cannot be assumed to be physical parts, since KiCad's actual source physical component export contains 36 not 40 parts. No BOM inflation is permitted.

## Verified failure controls

The audit explicitly and reproducibly refuses:
- Same library/value pair appearing multiple times on either side, including injected duplicate apparent matches;
- mismatch or duplication of source pin numbers;
- missing/mis-parented `schematic_port` identity;
- malformed/non-finite schematic component geometry;
- duplicated `source_component`, `source_port`, or other JSON identity fields;
- **hierarchical/multi-sheet visual assignments**, because this converter has no authoritative per-instance sheet scope.

Both original and shuffled input document order produce the **same 21 unique candidates**, and arbitrary drawing-position changes do not promote the remaining 15.

One adversarial test swaps the **coordinate centers of two converter schematic components** while leaving all metadata unchanged. The audit still reports 21 candidate identities. We intentionally test this to expose that **the current method cannot authenticate actual visual positions**. That is why `visual_geometry_merged=false`, `kicad_symbol_uuid_authenticated=false` and `automatic_fabrication_authorized=false` are fixed authority gates.

## How to reproduce

Requires `kicad-cli`, Node/npm and the actual upstream converter dependency installed in `examples/integrations/kicad-circuit-json/`.

```bash
cd examples/integrations/kicad-circuit-json
npm install --no-audit --no-fund
npm run convert -- \
  ../../../hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_sch \
  /tmp/spi-upstream-geometry.json
cd ../../..
python examples/integrations/kicad-circuit-json/audit_geometry_identity.py \
  --schematic hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_sch \
  --converter-json /tmp/spi-upstream-geometry.json \
  --out /tmp/spi-geometry-identity-audit.json
pytest -q tests/test_kicad_geometry_identity_audit.py
```

The CLI invokes official KiCad independently, computes source and converter hashes, outputs all candidate/ambiguous source references, and never makes a design change.

**77 integration/regression tests passed**, including actual KiCad 9 / upstream converter visual audit, official three hierarchical demo exports from `kicad-demos`, existing Circuit JSON interoperability and netlist checks. Full GitHub CI is a separate release gate.

## Real competitive significance and next gate

HS now distinguishes **three** levels of source confidence:
- **Verified source electrical connectivity:** actual KiCad netlist, exact REF.PIN and net-name parity, as tested in PR #209/#210.
- **Candidate visual component identity:** unique library/display-value and exact pin-number correlation, 21/36 on this schematic; not UUID authenticated.
- **Unverified visual placement and remaining identities:** converter schematic geometry, duplicate components and hierarchical scopes remain quarantined.

Next substantive work should add **an upstream-format/native KiCad symbol UUID + sheet-instance mapping** (perhaps upstream converter integration or a properly source-grounded extension), then prove coordinate transforms and port placement against KiCad's original symbol coordinates. Only after exact independent mapping should visual geometry be merged with verified electrical connectivity.

No physical repair, manufacturing, PCB design correctness, source geometry parity, monetary savings, or competitive product superiority is demonstrated by this partial metadata audit.
