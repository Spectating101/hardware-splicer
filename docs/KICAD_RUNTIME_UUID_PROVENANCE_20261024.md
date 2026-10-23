# KiCad native symbol UUID provenance — converter runtime capture

**Executed:** 2026-10-24. **Status:** actual upstream converter-runtime UUID map captured and independently reconciled with original KiCad source and KiCad CLI export; **not** cryptographically signed converter output, independently verified wire geometry, authorized manufacture, or a multischeet converter identity solution.

## Discovery that changed the strategy

The pinned `kicad-to-circuit-json@0.0.144` converter **already contains** a map at `converter.ctx.symbolUuidToComponentId`. The schematic `CollectLibrarySymbolsStage` uses `symbol.uuid` from its parsed KiCad model and associates that UUID with the newly inserted `schematic_component_id`. That information is **not written to standard Circuit JSON**, which is why our previous PRs (#211–#213) had to derive candidate component identities using library/value, native positions and pin-center geometry.

Rather than guess component provenance from positions, this PR captures the original mapping **inside the live converter process**, creating a separate hash-bound sidecar while retaining the standard Circuit JSON *byte-identically unchanged*. The companion includes original KiCad UUID, real reference designator, one native instance's project, sheet UUID path, unit, symbol library name, generated schematic and source component IDs, and source pin numbers.

This is *converter-runtime* provenance, not a fork of the upstream library or a new Circuit JSON standard field. The installed converter version is pinned; `ctx` is an internal API and may change. The capture **fails closed** if the map is absent, incomplete, duplicated or ambiguous.

## Actual same-source independent result

Ran actual `kicad-to-circuit-json@0.0.144` and independent KiCad **9.0.8** netlist export on `hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_sch`. HS compared raw native source, official export, unchanged converter documents and UUID sidecar.

| Verification | Executed |
| --- | ---: |
| Unmodified upstream Circuit JSON records | **679** |
| Upstream visual symbols with direct runtime UUID mapping | **40/40** |
| Original physical KiCad components with UUID checked against independent KiCad netlist `tstamps` | **36/36** |
| Additional non-physical `power:PWR_FLAG` schematic symbols (excluded from physical BOM) | **4** |
| Native KiCad project + sheet UUID instance paths checked | **40/40** |
| Converted visual `schematic_port` records assigned to verified components and source ports | **83/83** |
| Physical source port numbers independently reconciled to KiCad net names | **79/79** |
| Verified automatic wire geometry / schematic junctions | **0** |
| Native multischeet converter-instance mapping demonstrated | **No** |
| Hardware repairs/fabrication authorized | **No** |

The original ordinary converter command and `convert:provenance` produce **byte-for-byte identical Circuit JSON** for this source. Capturing metadata does not alter external Circuit JSON.

For example, U1 pin 1 maps to official KiCad `/3V3` using KiCad netlist `REF.PIN` membership, while the converter's native UUID links the correct U1 source and schematic record. Four extra power-flag symbols remain nonphysical and have no asserted physical net labels.

### Actual user-facing integration

`examples/integrations/kicad-circuit-json/convert_with_provenance.mjs` invokes the pinned upstream converter and saves a **companion** JSON provenance file. `src/hardware_splicer/integrations/kicad_runtime_uuid_provenance.py` independently checks that file against the native original, official KiCad netlist, source/schematic component references, port identities, and SHA256 hashes. It then generates an optional **read-only source-backed label overlay**, not a fabricated merged electrical circuit.

`examples/integrations/kicad-circuit-json/verify_uuid_overlay.py` executes KiCad CLI for the independent source export, validates the sidecar and emits per-component/per-port labels and net names:

```bash
cd examples/integrations/kicad-circuit-json
npm install --no-audit --no-fund
npm run convert:provenance -- \
  ../../../hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_sch \
  /tmp/circuit.json /tmp/native_uuid_sidecar.json
cd ../../..
python examples/integrations/kicad-circuit-json/verify_uuid_overlay.py \
  --schematic hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_sch \
  --circuit-json /tmp/circuit.json \
  --provenance /tmp/native_uuid_sidecar.json \
  --out /tmp/verified_visual_source_labels.json
```

The resulting output contains source UUID / reference / sheet path → actual converter component ID → converter port ID → independent KiCad net name. **It does not read electrical net membership from converter `schematic_trace` coordinates** or alter the generated Circuit JSON itself.

## Intentional security and correctness boundaries

The validator rejects: swapped native UUIDs (including identical-value resistors), a forged schematic-component linkage, duplicate/missing mappings, incorrect sheet paths, altered source hashes, altered pin numbers, mismatched visual/source-port parent links, and changed original Circuit JSON even when the altered digest has been recomputed.

The provenance companion contains SHA256 hashes but is **not cryptographically signed**. A malicious actor controlling both the converter process and output could forge a convincing sidecar; execution of the pinned upstream package in an authorized isolated environment provides a reproducible provenance process, not a cryptographically verifiable third-party attestation.

The **native symbol UUID from KiCad** is checked against the official KiCad netlist export for actual physical components. For schematic-only power flags, source UUID and path are corroborated by the native `.kicad_sch` input; those symbols are not represented as physical parts in the KiCad export.

The current converter handles a **single source sheet with exactly one native instance path per symbol**. We deliberately reject multiple native instance paths, because a per-symbol UUID alone does not distinguish which repeated hierarchical occurrence produced each visual. PR #210 separately demonstrated official *electrical* hierarchy recovery, **not** multischeet converter visual provenance.

Finally, **provenance of a visual record does not prove that its schematic trace geometry faithfully represents the electrical netlist**. PR #213 independently proved native pin-center positions for the 79 original pins, but upstream `schematic_trace` wire/junction visual semantics remain a distinct proof gate. No automatic wire reconstruction, ERC/DRC, manufacturing approval, or repair-success claim follows.

## Actual regression evidence

**131 focused Python tests passed** with KiCad 9.0.8, official KiCad demo sources and real upstream converter v0.0.144, including native UUID tamper checks, visual source overlay, previous pin-center geometry, repeated-channel KiCad hierarchy, Circuit JSON interchange, and repair-electrical evidence.

Machine-readable actual result: `benchmarks/kicad_runtime_uuid_provenance_20261024/actual_converter_runtime_uuid_execution_receipt.json`.

**Next hard gate:** use the authenticated **UUID-linked visual source-port ↔ KiCad REF.PIN/net crosswalk** to check each upstream converter `schematic_trace` segment/junction against KiCad's **native wire, label and junction objects**, including crossing-without-connection, multiple net labels and repeated sheet instances. Keep unverified visual wires quarantined.

**Verdict:** Original converter record identity is now preserved and independently checked for the tested single-sheet schematic. This removes the earlier position-guessing identity blocker, but not the independent wire-geometry or multischeet provenance gates.
