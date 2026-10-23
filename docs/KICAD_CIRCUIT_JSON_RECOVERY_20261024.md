# HS Competitive Interchange Challenge — KiCad → Circuit JSON topology recovery

**Date:** 2026-10-24. **State:** real software experiment executed and source-level parity verified; **not** recovered converter geometry, PCB fabrication, or an independent third-party competitor win.

## Engineering failure verified first

The real open-source `kicad-to-circuit-json@0.0.144` converter was run on
`hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_sch`.
This produced the following Circuit JSON source documents:

| Raw converter record type | Count |
| --- | ---: |
| `source_component` | **40** |
| `source_port` | **83** |
| `source_net` | **16** |
| `schematic_trace` | **87** |
| **`source_trace`** | **0** |
| All other schematic visual records | Remaining of **679** documents |

`source_net` records carry names but no port memberships (`member_source_group_ids: []`); `schematic_trace` records carry 2D `edges`, not `connected_source_port_ids`. The existing HS `circuit_json_to_netlist` therefore imported **40 components but 0 connected nets / 0 source pin memberships**. The real `POST /v1/interchange/circuit-json/inspect` returned **HTTP 200, status=blocked, compilable=false**. This is **not** a valid electrical design import.

**Do not infer connectivity from visually nearby schematic lines, coordinates or matching net names.** Such reconstruction may be possible after a separate, validated geometry interpretation step, but was not attempted as authoritative electrical truth here.

## What HS now reuses instead

A new **source-authoritative recovery bridge** `src/hardware_splicer/integrations/kicad_circuit_json_recovery.py` reads an actual KiCad netlist export using HS's corrected S-expression importer (PR #208), then produces a *separate* Circuit JSON document array containing:
- 1 `source_component` per KiCad exported reference (real `R1`, `C2`, `U1`, etc.),
- 1 `source_port` per unique original `REF.PIN`,
- a `source_net` per original electrical net, and `source_trace` records linking the known ports only where **2 or more** real pin members exist,
- a fail-closed source-versus-reimported netlist parity check on **net name and complete sorted member REF.PIN set**, alongside consistent component count,
- separate tracking of true KiCad single-pin unconnected nets, **without fabricating second pins**.

It then runs the **existing HS Circuit JSON importer on its own normalized output** and rejects the output if any original connected net membership changes.

This repairs the interoperability workflow by **using official KiCad as the electrical source of truth**. It does *not* repair `kicad-to-circuit-json` itself, establish any one-to-one mapping between its rendered symbols and KiCad physical component references, or merge converter schematic geometry. Original converter output remains blocked.

## Genuine actual-source head-to-head, same schematic

I installed **KiCad 9.0.8** in the test environment and invoked its real CLI:

```bash
kicad-cli sch export netlist --format kicadsexpr \
  --output /tmp/official-spi-flash.net \
  hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_sch
```

The upstream converter and KiCad export were generated from the **identical checked-in schematic**.

| Verification | Official KiCad export | Recovered Circuit JSON through HS | Raw external converter through HS |
| --- | ---: | ---: | ---: |
| Components | **36** | **36** | **40** |
| Net documents | **19** | 19 source_net docs | 16 source_net docs |
| Truly connected multi-pin nets | **16** | **16** | **0 imported** |
| Connected pin memberships | **76** | **76** | **0 imported** |
| Explicit unconnected 1-pin net members | **3** | **3 retained in source metadata / receipt** | Not proved |
| Exact multi-pin net + pin parity to KiCad | Reference | **Yes** | **No** |
| HS `/inspect` outcome | N/A | `status=ready; compilable=true` | `status=blocked; compilable=false` |

The original 79 KiCad net-pin memberships are **76 members of connected nets + 3 single-pin NC members**. Those three are preserved as an explicit receipt; they are not inserted as fake multi-pin connections.

The converter's four extra `source_component` records are the four `power:PWR_FLAG` schematic symbols in the original source (KiCad excluded these from its exported physical component section). Its 16 net **names** match the 16 connected KiCad net names after removing the KiCad *root-sheet* `/` scope prefix. This corroborates the intended labels, **but still does not prove converter source-port↔KiCad pin correspondence**. The receipt explicitly says `geometry_and_component_identity_reconciled=false`.

The normalized source array sent to `POST /v1/interchange/circuit-json/inspect` returned **HTTP 200; 36 imported components; 16 imported nets; compilable=true**. That is *source-interchange readiness*, **not proof of independently correct routing, ERC/DRC, board manufacturing, hardware repair, or physical performance**. The output remains `fabrication_authorized=false`.

Actual deterministic report: `benchmarks/kicad_circuit_json_recovery_20261024/actual_spi_flash_execution_receipt.json`. The official KiCad export embeds local paths/time and is reproduced rather than committed.

## Reproduce

With repository installed `pip install -e '.[dev]'`, Node/npm and genuine KiCad CLI available:

```bash
cd examples/integrations/kicad-circuit-json
npm install --no-audit --no-fund
npm run convert -- \
  ../../../hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_sch \
  /tmp/upstream_converter.json
cd ../../..
python examples/integrations/kicad-circuit-json/recover_connections.py \
  --schematic hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_sch \
  --converter-json /tmp/upstream_converter.json \
  --out /tmp/hs_source_connected.json \
  --receipt /tmp/hs_topology_parity.json
pytest -q tests/test_kicad_circuit_json_source_recovery.py \
  tests/test_circuit_json_interoperability.py
```

You may also provide an already exported source netlist through `--netlist-export`, but that forfeits the script's direct `kicad-cli` execution guarantee. Without a genuine netlist, this recovery mechanism **refuses to manufacture source wiring from visual linework alone**.

## Validation and limitations

- **78 targeted tests passed** on a sandbox with KiCad 9.0.8, including actual official source export, exact 36/19/79 raw mapping, exact 16-net/76-connected-pin roundtrip, malformed or contradictory source rejection, existing Circuit JSON interoperability, and repair-electrical evidence checks.
- `kicad-to-circuit-json` itself remains usable for component/schematic visual features but its component/port IDs have **not** been matched to the authoritative KiCad designators and pins.
- This test uses one **HS-maintained schematic**, not independent third-party electrical design projects; a broader format-coverage corpus (multi-sheet, hierarchical nets, global labels, buses, hidden power pins) is required before general export parity can be claimed.
- No physical hardware examined; no real repair result, no electrical safety approval, no economic advantage or commercial competitive victory demonstrated.
- Full GitHub CI and the wider PR stack remain separate merge gates.

## Next productive challenge

1. Build tests for multi-sheet and hierarchical KiCad exports and part reference identity, then measure whether source parity survives them.
2. Keep converter visual geometry quarantined until a verified `schematic_component`↔KiCad reference/pin mapping can be proven by source UUID, symbol IDs and independent KiCad parser evidence.
3. Once import is trustworthy, independently validate component choice, netlist-to-PCB routing, BOM conservation and physical test procedures against a suitable competitor.
