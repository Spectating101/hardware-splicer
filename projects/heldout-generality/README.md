# Hardware Splicer — genuinely held-out PCB generality + replay (v1)

**Scope:** bounded, source-backed digital verification of unfamiliar KiCad boards.
This is **not** an autonomous board editor, universal physical probe fixture,
manufacturing package, powered bench run, or commercial/third-party evaluation.

## Cohort and leakage control

The external [punkfab/pcb-corpus](https://github.com/punkfab/pcb-corpus)
contains 235 KiCad 9 boards from 170 upstream repositories with their original
project-specific DRC rules. **No corpus boards are vendored into HS.**

The frozen `cases.lock.json` pins the exact corpus commit, manifest SHA-256,
source-repository commits and SHA-256 of each PCB, project, custom DRC file,
source attribution and available license file. The script `freeze.py` created
this lock once. The ordinary runner **never selects replacements**.

Selection, pre-registered before the first run: SHA-256(seed+board ID), first
two from each 2-layer/4-layer × originally DRC-clean/dirty stratum, with
one original repository per board, at least five parts, at most 450 pads and
1,100 segments. This deliberately limited eight-board **convenience
engineering sample is NOT representative of the full 235-board population**.

| Source | Layers | Original error-level DRC |
| --- | ---: | ---: |
| dnlbauer/corax-keyboard | 2 | 0 |
| rniwase/sdtv2csi | 2 | 0 |
| DIYSynthMNL/Eurorack-Multi-Saturation-Module | 2 | 1 |
| TweetyDaBird/Little-Big-Scroll | 2 | 7 |
| justbuchanan/oasis | 4 | 0 |
| protolux-electronics/trellis_core | 4 | 0 |
| brenocq/bldc-motor | 4 | 4 |
| Miceuz/rs485-moist-sensor | 4 | 222 |

## What the frozen pilot actually checks

1. Read the original bytes directly from the exact Git corpus commit, not its
   possibly modified working directory. Reject missing or changed hashes.
2. Copy original `board.kicad_pcb`, `board.kicad_pro`, optional
   `board.kicad_dru`, source attribution, and license into new per-run inputs.
3. Execute KiCad 9 `pcb drc --severity-error --format json` under those
   original project rules. Preserve native output; independently summarize
   error-level violations and unconnected items. *Dirty original boards are
   expected dirty*, never upgraded to clean or silently fixed.
4. Execute pinned KiSkill `kx check` as optional structural parser. A tool
   failing to parse an unfamiliar file is an explicit negative result.
5. On every originally clean board, generate one **deliberately invalid**
   same-layer, cross-net copper bridge using native pcbnew on a copy; rerun DRC
   and demand an **increased error count**. No faulty file is source or fab.
6. Independently repeat the full test in two new round directories. Compare
   **semantic findings, input hashes, source classes, mutation identities and
   admission decisions**. Raw CLI DRC report files include clock timestamps
   and cannot be byte-identical; that is why the canonical semantic digest
   explicitly excludes timestamps and filenames.
7. Export the exact aggregate report and retained per-case receipts, with
   both successful and failed cases. Exit nonzero if the digital gate or
   repeatability fails. Refuse reuse of an existing output folder.

### Discovered repeatability defect

The first two-pass run correctly passed all eight original source cases and
four injected short controls, **but failed repeatability**: KiCad emitted
three fault errors in one repeat and two in another on the rniwase board.
A newly created pcbnew trace received a random KIID, affecting DRC finding
deduplication. The mutator now stamps only this newly synthesized trace with
a deterministic source-and-net-bound UUID before its DRC replay. The first
non-repeatable result is retained as a documented failure, not overwritten.

## Final executed result — Optiplex, 20 November 2026

**PASS (bounded digital review):** both independent fresh result folders
produced the identical canonical SHA-256
`61a3ce8162fc9e98640858ed60f3442d62053ab5da08f94659e65ad293100db8`.
KiCad 9.0.2 checked the exact 0, 0, 1, 7, 0, 0, 4, 222
original error counts; all eight KiSkill structural parses passed; all four
cross-net shorts were detected in **both** rounds. Twelve offline regression
tests passed. The independent `audit.py` verified original source hashes,
each original DRC report and eight fault-control results and returned PASS.
See `evidence/benchmark-result.json`, the two exact per-case summaries,
`evidence/independent-audit.json`, and the preserved original failing
replay receipt `evidence/initial-failed-repeatability.json`.

**Not yet demonstrated:** second-machine reproduction, source-to-schematic
parity, functional edit generality, generalized STEP probe-fixture design, or
physical measurements.

## Reproduce in a clean isolated checkout

Requires Linux with KiCad 9 CLI and `/usr/bin/python3` able to import
`pcbnew`. Use a fresh HS worktree at the commit containing this pilot.
Fetch external corpus without checking out all PCB blobs:

```sh
git clone --filter=blob:none --no-checkout https://github.com/punkfab/pcb-corpus.git /tmp/hs-pcb-corpus
git -C /tmp/hs-pcb-corpus sparse-checkout set --no-cone README.md
git -C /tmp/hs-pcb-corpus checkout --detach 1e999b4eefd5fdfcc90dc376d2882390245a8e0d
```

For a full pinned KiSkill check, clone
[KiSkill](https://github.com/AvatarSD/KiSkill) at
`b27ce9e0f7bee10ef6dd606baabcbaf0c3c1eecc` with a clean checkout,
review upstream executable first, then:

```sh
PYTHONPATH=src python3 projects/heldout-generality/run.py \
  --corpus-repo /tmp/hs-pcb-corpus \
  --kiskill-repo /path/to/pinned/KiSkill \
  --out /tmp/hs-heldout-first
PYTHONPATH=src python3 projects/heldout-generality/test_benchmark.py
PYTHONPATH=src python3 projects/heldout-generality/audit.py \
  --out /tmp/hs-heldout-first
```

If KiSkill is omitted, the runner records `NOT_CONFIGURED` and cannot
declare overall digital success. All checkers execute only on extracted copies
in new folders but **they are not OS-sandboxed**. Use trusted source and
stronger isolation for private or untrusted customer designs.

## Evidence semantics and limitations

- An error-free original native DRC means only that KiCad finds no
  **error-level** DRC violations under that project's rules and KiCad version.
  It does **not** validate circuit intent, EMC, ESD, power ratings or safety.
- This corpus does **not** include original schematics; `akcli` schematic-to-PCB
  verification is **NOT TESTABLE** here. Reporting equivalence would be false.
- The preexisting HS `bench-probe-fixture` can only parse a narrow class of
  rectangular TP/H boards. This pilot **does not generalize fixture CAD** to
  irregular shapes or validate fit, probe pressure or manufacturing repeat.
- A clean 8/8 is a demonstration of **EDA import, project-rule preservation,
  source integrity and injected fault rejection**, not a statistically
  justified success rate for arbitrarily new boards.
- No original board was modified, physically handled, energized, fabricated,
  sold, or approved for manufacturing.
- The runner is opt-in and does not alter any active HS ProjectStore, default
  branch, live UI, external adapter installation or Policy Lab state.

## Engineering acceptance gates for the *next* milestone

Expand beyond this narrow sample with precommitted high-risk strata
(custom rules, complex cutouts, 4-layer planes, legacy KiCad). For each new
case, compare against expert judgment on a proposed *functional* edit and a
source-bound 3D fixture; assess labor/time and user reproducibility in a second
environment. Keep a full engineering test/lab build HOLD until independently
verified mechanical fit and physical measurements exist.
