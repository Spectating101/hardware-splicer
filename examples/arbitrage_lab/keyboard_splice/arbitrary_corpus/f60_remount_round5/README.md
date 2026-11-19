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


## Stage VIII — recovering the legacy KiCad DRC, confirming Teensy pinout, halving junction area (2026-11-16)

These results **supersede the earlier source DRC timeout notes above**, but do not grant physical manufacturing approval.

### 1. Native KiCad 9 refills the original two netless legacy zones

The original byte-identical 2017 f.60 KiCad board was still hanging during native KiCad 9 DRC. HS now provides `scripts/hs_verify_legacy_zone_drc.py`, a source SHA-256 checked operator that:

1. Loads the exact original source file **without modifying it**.
2. Saves a separate temporary copy after un-filling and regenerating its two inherited copper polygons with native KiCad's zone filler.
3. Compares the original and converted board's **485 pads, 489 copper track segments, 18 vias, 129 footprint locations and 62 keys** as unordered electrical geometry (rejecting any changed copper/terminal).
4. Runs **full-severity native KiCad 9 DRC on the converted copy**, recording all original warnings and errors.
5. Keeps only frozen DRC/geometry receipts in HS (no derivative third-party KiCad PCB is published).

Measured results: **0 DRC errors, 0 unconnected items and 321 warnings** after refill. Warnings are **200 `silk_over_copper` and 121 `lib_footprint_issues`**. The source polygon fills are **not byte-identical** after reconstruction, and the warnings and original-source quality still require resolution. The prior 65-second native DRC timeout is isolated to the legacy filled-zone representation; the recovered, converted-source DRC is a meaningful electrical-model check but **not a clean physical production release**.

Reproduce on the SHA-pinned upstream PCB:

    PYTHONPATH=src python scripts/hs_verify_legacy_zone_drc.py \
      --pcb /path/to/f60.kicad_pcb \
      --expected-sha256 e0c605a421dec0e88264beb50f5c3ad58b37a0c20294703e6d8637c0f8613cd6 \
      --out /tmp/zone_drc_refilled_copy_receipts

Frozen details: `legacy_zone_drc_round9/LEGACY_ZONE_DRC_RECEIPT.json` and `legacy_zone_drc_round9/NATIVE_REFILLED_COPY_DRC.json`.

### 2. Original Teensy 2.0 C pinout checked independently

The original source-owned `Teensy_20.kicad_mod` footprint (SHA-pinned in `SOURCE_PIN_MANIFEST.json`) was reconciled with the original PCB's **31 U1 pad locations** and the official [PJRC Teensy 2.0 C-language pinout card](https://www.pjrc.com/teensy/card2a_rev5_web.pdf).

All **19 original TMK firmware row/column GPIOs** resolve to the correct Teensy 2.0 KiCad physical pad numbers: 5 scan rows and 14 scan columns. No pin swaps were required in the modeled restoration. Evidence: `PJRC_TEENSY2_PINOUT_PROOF.json`.

This confirms the *source reference's static pin assignment*; it **does not test a Teensy device, firmware binary, USB power or diode condition**.

### 3. Compact 2×25 IDC alternative junction: 49.1% less board area

The earlier 20-group source-net junction needed a ~195 × 39.78 mm PCB for 49 physical wire terminals. The new `keyboard_splice_compact_junction.py` generates a **42 × 94 mm** native KiCad board using the standard KiCad `IDC-Header_2x25_P2.54mm_Latch_Vertical` footprint.

- All **20 original source-net groups** are preserved and never cross-shortened.
- There are **49 used header pins** (39 distinct donor terminals plus 10 relocated-key contacts). Header pin 50 remains unassigned.
- The grouped 20-net IDC PCB passes native KiCad 9 **full DRC with zero errors, warnings or unconnected items**.
- Area comparison: **7,757.1 → 3,948 mm²**, a **49.1% nominal PCB area reduction**.
- This single compact junction is an **alternative to both** the large unified junction and original 17-channel interposer. Do **not** install these boards together.

Artifacts: `compact_idc50_round8/compact_idc50_junction.kicad_pcb`, `COMPACT_JUNCTION_WIRING.json`, `COMPACT_JUNCTION_VERIFICATION.json` and `NATIVE_COMPACT_DRC.json`.

The design is not a verified commercial IDC component selection, stock BOM, low-stress ribbon routing or mechanically constrained enclosure. All cable mating, insulation, source solderpad accessibility, support, and physical testing remain pending.

### Single source-bound HS engineering run with these added proofs

After the DRC diagnostic above and with all **six exact upstream files** from `SOURCE_PIN_MANIFEST.json` available locally, run the Stage VII command and additionally pass:

    --source-teensy2-footprint /tmp/f60_upstream/Teensy_20.kicad_mod \
    --pjrc-pinout-proof-json /tmp/f60/PJRC_TEENSY2_PINOUT_PROOF.json \
    --legacy-zone-drc-receipt-json /tmp/zone_drc_refilled_copy_receipts/LEGACY_ZONE_DRC_RECEIPT.json \
    --compact-junction-out /tmp/f60/compact_idc50

All seven source-bound evidence items are recorded in the canonical HS MachineProject; the status remains **DESIGN_READY modeled, BUILD_READY denied**.

**Physical constraint:** This remains a conditional virtual design for a known source PCB, not proof that arbitrary physically discarded keyboards can be cut, rewired and sold reliably.
