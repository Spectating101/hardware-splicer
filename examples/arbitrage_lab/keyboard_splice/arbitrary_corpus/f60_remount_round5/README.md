# f.60: conditional 62-position virtual reconstruction with key relocation

**Original external design:** [robertcalvert/f.60](https://github.com/robertcalvert/f.60), `hardware/keyboard.kicad_pcb`, exact source SHA-256 `e0c605a421dec0e88264beb50f5c3ad58b37a0c20294703e6d8637c0f8613cd6`.

This is a source-bound virtual salvage investigation, **not a real used keyboard or a physically validated conversion**. The original KiCad design is not copied into the HS repository. Obtain and SHA-check the exact public reference when reproducing.

## Actual generated work

HS tried **12 automatically parameterized cut strategies** and retained **10 distinct** candidate routes. The selected model cut divides the original PCB into halves containing 24 and 33 retained key positions. It intentionally retires five original switch *positions* that would collide with the saw path: **K15=T, K25=G, K36=B, K[0]5=5, K[0]6=6**.

HS then generated:
- `interposer/reference_bridge_interposer.kicad_pcb`: editable native KiCad **17-channel** electrical-restoration PCB for the source-bound modeled severed nets; native DRC **zero violations/zero open items**.
- `key_remount/remount_keys.kicad_pcb`: editable native KiCad **five-switch relocation PCB** using actual Cherry MX footprint geometry, with **five separately numbered 2-pin headers** and two independent circuits per switch; native DRC **zero violations/zero open items**.
- `key_remount/RELOCATION_MAP.json`: ten source PCB pad-to-remount header wire assignments. Every original source net and pad location is recorded from the upstream reference; no hand-written *new* net mapping is substituted.
- `MULTI_ROUTE.json`: all 12 strategy results, selected path and exact switch/pad/via loss audit.
- `POSTCUT_ISLANDS.json`: 17 candidate restoration edges and **0 remaining required modeled copper groups** after graph replay. Source preexisting terminal gaps are **0** in the affected-net model.
- `ORIGINAL_SOURCE_DRC_STATUS.json`: explicit *unknown/failure* state for the original 2016-era board under KiCad 9 (65-second bounded check timed out).
- `SUMMARY.json`: conservative progress/verification receipt.

Thus **57 original key positions on the reused halves + 5 reference switch positions remounted = 62 original reference switch positions accounted for** in the virtual assembly.

## Repeat it in HS

    PYTHONPATH=src python scripts/hs_keyboard_splice_probe.py \
      --pcb /path/to/exact/f60.kicad_pcb \
      --out /tmp/f60/CUT_OVERVIEW.json \
      --optimize-stepped --multi-route-json /tmp/f60/MULTI_ROUTE.json \
      --stepped-path-json /tmp/f60/STEPPED_CUT.json \
      --repair-mode auto --repair-iterations-json /tmp/f60/REPAIR_ITERATIONS.json \
      --postcut-islands-json /tmp/f60/POSTCUT_ISLANDS.json \
      --postcut-edges-csv /tmp/f60/BRIDGE_CANDIDATES.csv \
      --machine-project-json /tmp/f60/MACHINE_PROJECT_HANDOFF.json \
      --interposer-out /tmp/f60/interposer \
      --key-relocation-out /tmp/f60/key_remount

## What this **does not** establish

The original source PCB's legacy KiCad DRC did **not** finish. The f.60 reference also contains variant footprints, and we have not checked any actual recycled switch/board population, original MCU firmware behavior, assembly, wire termination, cable strain relief, USB supply/ESD, enclosure, commercial margins or real repairs.

The 17-channel bridge is not automatically mated to the ten-wire daughterboard. Original switch pads must be inspected, physically connected, mechanically secured and tested after any real cut. Nothing has been fabricated, ordered or powered.

**Verdict: `CONDITIONAL_SOURCE_REFERENCE_RELOCATION_PREVIEW`, not build-ready.** This is a stronger virtual design than the previous five-lost-keys case, but the original eight-board strict acceptance result remains **0/8**, and no model result is automatically promoted to real physical acceptance.


## Stage VII: independent original firmware, full matrix and unified wiring bus (2026-11-16)

The original-source validation now uses **three distinct inputs** that were not used to create the earlier cut geometry: the upstream `hardware/keyboard.net` schematic export, upstream `firmware/matrix.c`/configuration/keymap, and the actual preserved source PCB pad names. Each upstream file's exact SHA-256 is pinned in `SOURCE_PIN_MANIFEST.json`. The raw third-party firmware and schematic are **not stored in HS**.

**Source and firmware audit results:**

| Independent proof | Actual result |
|---|---:|
| Source schematic nets | 93 |
| Source schematic endpoints | 279 |
| Connected schematic pad assignments matching PCB | **267/267** |
| Schematic-only controller no-connect terminals | 12 (not connected keys) |
| Firmware controller matrix | **5 rows × 14 columns** |
| Source switches matching a unique matrix address/diode | **62/62** |
| Default firmware keymap physical positions | **62/62**, three keymap layers |
| Simulated ideal switch closures | **91,230** |
| Ideal switch mismatches | **0** |
| Original firmware compiled, flashed and run on hardware | **No** |

The 91,230 simulation patterns comprise all individual keys, all 1,891 pairs, all 37,820 triples, every subset pressed within any one source row (49,408 patterns), 2,048 seeded multi-key combinations and the idle state. The source-diode-to-row assumption is explicitly recorded; testing ideal switch closure does **not** establish real diode condition, debounce, timing, electrical current limits or USB behavior. The 62 source matrix addresses are compared to the actual upstream TMK `KEYMAP` indexing and controller row/column scan GPIO declarations.

The five relocated key identities are independently corroborated by original firmware: `K15 → T`, `K25 → G`, `K36 → B`, `K[0]5 → 5`, `K[0]6 → 6`.

### Full 49-terminal unified harness junction

A new alternative native KiCad board, `full_junction/keyboard_recovery_junction.kicad_pcb`, joins the original cut-net repairs and the relocated-key terminals into **20 separately routed source-net groups**. Its exact source contact assignment is in `FULL_JUNCTION_WIRING.json`.

- **39 distinct donor PCB pad contacts** (one physical donor solder connection per distinct pad);
- **10 five-key-daughterboard connector contacts**;
- **49 terminals** on 20 grouped connector footprints;
- Measured *design* board footprint approximately **195 × 39.78 mm**;
- Native KiCad DRC **0 violations and 0 unconnected items**.

**This junction replaces the separate 17-channel cut-net interposer for a possible unified assembly; DO NOT install both in parallel.** It is a DRC-checked prototype to make the actual source and daughterboard wire inventory unambiguous—not a compact product PCB, qualified connector, flexible cable, mechanically supported enclosure, or physically demonstrated repair.

The HS canonical MachineProject now includes this source-derived original keymap audit, a 62-key simulated proof, the unified harness junction, extra proposed subsystem interfaces, and its original blocked electrical bench verification. It remains **DESIGN_READY only**: the BUILD_READY request is refused.

### One-command replay against the exact upstream files

Assuming a separately fetched SHA-identical f.60 PCB and the five pinned upstream files in `/tmp/f60_upstream`:

    PYTHONPATH=src python scripts/hs_keyboard_splice_probe.py \
      --pcb /path/to/f60.kicad_pcb \
      --out /tmp/f60/CUT_OVERVIEW.json \
      --optimize-stepped --multi-route-json /tmp/f60/MULTI_ROUTE.json \
      --stepped-path-json /tmp/f60/STEPPED_CUT.json \
      --repair-mode auto --repair-iterations-json /tmp/f60/REPAIR_ITERATIONS.json \
      --postcut-islands-json /tmp/f60/POSTCUT_ISLANDS.json \
      --postcut-edges-csv /tmp/f60/BRIDGE_CANDIDATES.csv \
      --machine-project-json /tmp/f60/MACHINE_PROJECT_HANDOFF.json \
      --interposer-out /tmp/f60/interposer \
      --key-relocation-out /tmp/f60/key_remount \
      --independent-source-dir /tmp/f60_upstream \
      --source-pin-manifest SOURCE_PIN_MANIFEST.json \
      --independent-source-audit-json /tmp/f60/INDEPENDENT_SOURCE_AUDIT.json \
      --full-matrix-proof-json /tmp/f60/FULL_MATRIX_SOURCE_PROOF.json \
      --full-junction-out /tmp/f60/full_junction

Reference fixtures, canonical handoff, source pin graph, original DRC failure receipts and all editable generated KiCad files are bundled in this folder. The source-only CI regression runs without importing or redistributing original third-party PCB and firmware files.

**Final status remains conditional source-reference engineering**, not manufacturing-ready or proof of arbitrary discarded keyboard conversion. The original f.60 legacy KiCad board's complete DRC still times out; this independent schematic/firmware agreement cannot substitute for physical interconnect reliability, clearance, diode/USB validation or real donor tests.
