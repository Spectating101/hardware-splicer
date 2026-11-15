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
