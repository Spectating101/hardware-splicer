# HS — source-bound arbitrary-outline fixtures, held-out pilot

**20 November 2026.** Separate draft milestone stacked on HS #366, #361 and #355.
It closes part of the previous **fixed four-hole rounded-rectangle geometry** gap,
but **does not** close the electrical autorouting, physical fit or fabrication gap.

## Frozen cohort, not a hand-selected success gallery

The original commit `1e999b4eefd5fdfcc90dc376d2882390245a8e0d`
of [punkfab/pcb-corpus](https://github.com/punkfab/pcb-corpus) supplies 235
published KiCad boards. Four originally DRC-clean boards were chosen in HS
#361 by a deterministic SHA-256 seed, precommitted long before this milestone.
**All four** were used with no post-outcome substitution.

| Frozen independent PCB | Original geometry | Source mounting | Digital STEP audit |
|---|---|---|---|
| dnlbauer/corax-keyboard | 85-vertex irregular keyboard, 1 internal contour | No named NPTH mount | PASS |
| rniwase/sdtv2csi | 40-vertex rounded contour | No named mount | PASS |
| justbuchanan/oasis | 39-vertex curved outline, 1 internal contour | One source M3 mount | PASS |
| protolux-electronics/trellis_core | 64-vertex rounded contour | Four named source mounts | PASS |

**4/4** frozen originals produced *native-source-bounded nonretaining tray
models* and independently audited STEP. No board source bytes were changed.
These are **not** PCB electrical modifications, standoff assemblies, clamps,
operating probe jigs or physical 3D-printed production kits.

## Implementation that actually ran

- `outline_source.py` uses actual KiCad 9
  `BOARD.GetBoardPolygonOutlines()`, rather than four-line hardcoded contours.
  It retains tessellated contour vertices, internal cutouts, native mounting
  footprints, original board SHA-256, and a bounded shape-size gate.
- `outline_cad.py` uses CadQuery/OpenCascade to make actual reimportable
  source-polygon reference boards (including source internal cutouts), and
  shallow *nonretaining* pocket trays, with a 0.6 mm **assumed** lateral margin.
  Any internal cutouts are omitted from the tray cavity on purpose; the tray
  does not claim to reproduce internal island support/retention or populated
  PCB clearances.
- `audit_outline_cad.py` does not import the CAD generator: it reopens STEP,
  compares source shoelace area (minus all cutouts), model bounding dimensions,
  native source SHA, physical-authority status, export digests, and actual
  simulated bare-board-to-tray intersection after nominal insertion. It
  refuses modified source, omitted internal cutouts/altered contour, and
  false fabrication authority as three negative controls per board.
- `run_outline_generalization.py` verifies the original locked Git commit
  and all original source SHA-256s, executes **two fresh, independent rounds**
  over all four frozen source projects, and records successes and failures
  without replacing any case.

**Result:** 4/4 source-to-STEP audits PASS; all 12 adversarial audit
substitutions fail closed. Two rounds produce identical canonical semantic
SHA-256:

`9426b927a2e36f2c053d6af2198b4d4d8c7c46635fb0a86991f916ff9ce29ce8`.

The generated STEP files may vary in byte headers or serialization between
runs. This milestone only asserts **matching source dimensions, modeled
geometry and semantic independent audits**, not bitwise identical STEP files
or actual mechanical fit.

## What explicitly still fails

The separate out-of-sample **electrical** trial tried to move named test pads
TP1–TP4 on rniwase's PCB with a native short F.Cu copper connection back to
the original contact location, across **64 test point / 0.3–1.2 mm direction
combinations**. **0 candidate passed unchanged KiCad error-level DRC.**
The source was not silently relaxed or altered, and no successful electrical
modification is claimed. Full attempts and verdict are committed in
`outline-generality-evidence/electrical-testpoint-relocation-*.json`.

The prior attempt to *add* a new test point also failed 60+65 test candidates.
Neither search is exhaustive of valid electrical routing; the missing
capability is an actual design-rule-aware electrical routing/rework engine.

## Reproduce on a second authorized machine

Requires Linux, native KiCad 9 pcbnew in `/usr/bin/python3`, `kicad-cli`
and independent CadQuery Python interpreter. The upstream corpus must be
checked out at the exact known commit.

```sh
git clone --filter=blob:none --no-checkout https://github.com/punkfab/pcb-corpus.git /tmp/pcb-corpus
git -C /tmp/pcb-corpus sparse-checkout set --no-cone README.md
git -C /tmp/pcb-corpus checkout --detach 1e999b4eefd5fdfcc90dc376d2882390245a8e0d

PYTHONPATH=projects/heldout-generality /usr/bin/python3 \
  projects/heldout-generality/run_outline_generalization.py \
  --corpus /tmp/pcb-corpus \
  --cad-python /path/to/cadquery/bin/python \
  --out /tmp/hs-new-outline-run

/path/to/cadquery/bin/python projects/heldout-generality/test_outline_generalization.py
```

The checked-in `outline-generality-evidence/` holds the **original boards,
project rule files, source attribution and source licenses** for local
independent review, exact source polygon records, STEP/STL design files,
independent audit receipts, and complete round summaries. The parallel
`hs-outline-generality-engineering-v1.zip` packages the inspectable
material for transfer to a reviewer.

## Boundaries and release HOLD

- The new engine supports single KiCad board islands with KiCad-provided
  polygonization and one or more validated internal cutout contours; any
  multi-island or oversized design fails closed.
- KiCad polygonization is **tessellated**, not a proof of analytic arc
  identity or precise milling tolerance. No measured board thickness,
  connectors, populated components, antennas, retention loads, fixture
  stiffness, thermal/ESD properties or human assembly work is known.
- The trays provide a conceptual shallow seat and intentionally ignore
  inner cutout island-support geometry. **No claim of physical board fit,
  ready-to-print assembly or safe powered work** is authorized.
- The earlier M3 drill-revision experiment in HS #366 remains separate and
  held from fabrication because of uncorrected source footprint-library
  identity and physical fastener clearance.
- No second machine independently reproduced these results, no fabrication,
  no printer run, no paid-user adoption. The active HS project store and
  live UI are unchanged.

**Next genuinely difficult target:** source-level mechanical tolerancing
(including populated keepouts and real edge clearances), then DRC-aware
electrical routing with controlled trace topology. Do not infer a universal
engineering system from 4 board-shape successes.
