# HS held-out functional change → native PCB → matching STEP fixture

**Status:** source-bound DIGITAL PILOT with explicit fabrication HOLD.
**Date:** 20 November 2026.
**Build target:** the original four clean boards pre-frozen in `cases.lock.json`
from external `punkfab/pcb-corpus`, not an opportunistically swapped source.

## Actual cohort result

| Independent held-out board | Layer count | Result | Why |
|---|---:|---|---|
| dnlbauer/corax-keyboard | 2 | **BLOCKED** | 26-piece non-rectangular contour unsupported |
| rniwase/sdtv2csi | 2 | **BLOCKED** | Rounded outline, but not four source-backed 2.7 mm NPTH mounting holes |
| justbuchanan/oasis | 4 | **BLOCKED** | Non-rounded-rectangle contour, 3 straight edges + 1 arc |
| protolux-electronics/trellis_core | 4 | **DIGITAL PASS** | Four source-verified 2.7 mm nonplated holes, four-arc rounded outline |

**Success = 1/4 originally clean held-out boards**, not 4/4 or 235/235.
Unsupported cases have signed-off *software verdicts*, not CAD outputs.

## Executed edit, not a design illustration

On `protolux-electronics/trellis_core` at upstream source commit
`db4fe71623c14bcea47d7457d0db4c99d3899124`:
- Input `board.kicad_pcb` is the actual source revision, SHA-256
  `3c640f77fb7e53b45115bb746899b73bd673e92b3919ef3056e4a0f0ba4f994d`.
- Native KiCad `pcbnew` modified **H1–H4 mounting bore diameters from
  2.7 mm to 3.2 mm**, representing an M3 clearance *candidate*. No
  original source track, original pad-net identity or hole center changed.
- Revised editable KiCad board SHA-256:
  `f80212680c43319b987b3a0a5ab8332612eec2bf4361f2f5e0ba4a309b3939f3`.
- Revised KiCad 9.0.2 DRC: **zero error-level violations, zero unconnected
  pads**. There are **97 warnings** vs **93 on original**; exactly four
  additional footprint-library mismatch warnings accompany the deliberately
  changed drill sizes. **This is not manufacturing readiness.**
- Actual CadQuery/OpenCascade exported three independently reopened single
  STEP solids: **M3 fixture carrier, through-hole inspection template, and
  nominal unpopulated reference board**, plus an unassembled exploded STEP.
  All four modeled hole centers were independently checked against native
  board hole objects at (±22, ±22) mm in a source-derived local frame.
- A separate native KiCad inspector verified 342 original pads/net identities
  and 620 original copper objects were preserved. A separate STEP inspector
  verified actual reopened circular faces/edges, thickness/bbox and four
  positions for the PCB, guide, and carrier. Three adversarial metadata
  substitutions (stale revision, moved hole claim, fabricated power authority)
  were all rejected.

Two full fresh runs produced the **same editable board SHA-256** and the same
canonical case verdicts:
`758bda9b945f6f49a53547a3764bfa24c190fad3e583336f65c1700ef31bd3b0`.
STEP file *byte hashes differ* between exports, though independent BRep
geometry audits and STL hashes are equal. Do not assert bitwise STEP identity.
**11 focused integration/evidence tests passed** on the exported package.

## Negative-control engineering work (preserved, not hidden)

In parallel, an attempt at a more ambitious *electrical* edit failed:
- rniwase: 60 automatic new exposed-TP + copper-route candidates; **0 clean**.
- protolux: 65 candidates; **0 clean**.
- rniwase: enlarging its six existing testpads through 18 variants; **0 clean**.
- rniwase: 100 new M2 tooling-hole candidate locations; **0 clean**.

These are bounded local engineering searches with actual native KiCad DRC,
not evidence that no solution exists. See `functional-mount-evidence/reports/failed_edit_attempts.json`.
They demonstrate that earlier HS success at *verifying* varied boards cannot be
equated with generalized *editing* or automated routing.

## Run the actual experiment from scratch

Requirements: Linux; KiCad 9 CLI and system `/usr/bin/python3` importing
`pcbnew`; a separate Python environment importing CadQuery. No network or
power-on occurs during execution **after pinned source content is present**.

```sh
git clone --filter=blob:none --no-checkout https://github.com/punkfab/pcb-corpus.git /tmp/hs-pcb-corpus
git -C /tmp/hs-pcb-corpus sparse-checkout set --no-cone README.md
git -C /tmp/hs-pcb-corpus checkout --detach 1e999b4eefd5fdfcc90dc376d2882390245a8e0d

PYTHONPATH=projects/heldout-generality /usr/bin/python3 \
  projects/heldout-generality/run_functional_mount.py \
  --corpus-repo /tmp/hs-pcb-corpus \
  --cad-python /path/to/cadquery/bin/python \
  --out /tmp/hs-mount-run-unique

/path/to/cadquery/bin/python \
  projects/heldout-generality/test_functional_mount.py
```

The cohort is checked against a **frozen** manifest and file digests.
The script refuses existing output directories and creates two completely
new source/candidate/CAD/audit rounds with exact per-board failure verdicts.

## Reviewable deliverables

`functional-mount-evidence/` retains:
- Editable revised native KiCad PCB and its original project rule settings;
- Four generated STEP models (3 individual + exploded) and two STL files;
- Four-hole source-to-model map, candidate BOM, assembly/fabrication HOLD;
- Native DRC all-severity report, original/edited hashes, independent
  native-source and independent reimported-STEP audit, adversarial controls;
- Both complete round verdicts and one honest aggregate result;
- Source attribution and upstream CERN-OHL-P-2.0 license.

Original upstream source boards are NOT vendored into the HS repo; the edited
board is a separately attributed third-party-derived review example.
The exact pinned source can be retrieved by the reproducible runner.

## Fabrication BUILD HOLD

1. **Resolve library mismatch:** the old M2.5 footprint identity remains
   attached to the modified 3.2 mm pad. Replace/reconcile with appropriate
   M3 footprint and independently rerun *all* ERC/DRC/geometry inspections.
2. **M3 fastener physical geometry:** screw-head/washer and standoff clearance,
   board-edge web width, hole breakout, placement tolerances, torque,
   material strength and component body/connector height remain unverified.
3. **Nominal mechanics only:** 1.6 mm reference board thickness, assumed
   polymer, support rigidity, 3.45 mm template bore and guide alignment are
   engineering assumptions, not measured or independently printed geometry.
4. **Electrical operation:** original circuit intent, RF/signal integrity,
   power isolation, grounding and operation are entirely outside this test.
5. **Outside repeat:** no independent second-computer checkout, fabricator
   review, board print, bench instrument, assembled fixture, human work
   measurement, or customer acceptance has been demonstrated.

**Disposition:** keep as a reviewed digital pilot on a stacked DRAFT PR,
not as a generalized autonomous PCB editor, an M3 upgrade kit for sale, or a
physically safe lab instrument.

## Next generality threshold

Add exact arbitrary `Edge.Cuts` curve/slot/cutout support, multiple mounting
topologies and mechanically meaningful editor goals; force fail-closed DRC,
source hash and independent STEP checks across a larger frozen cohort. The
real advance requires at least one independently verified new *electrical*
functional edit and a fabricated, measured fixture on permitted hardware.
