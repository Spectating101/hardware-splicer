# Hardware Splicer milestone v3: source contour, actual signal branch, probe CAD

**20 November 2026. Digital-only prototype — neither electrical power-up nor
fabrication authority.** Stacked directly on HS #366, which in turn is stacked
on #361 and #355. All changes are isolated from the main integration/UI work.

## Why this is a substantive milestone

The previous #366 holder only supported four segment / four arc rounded
rectangles with exactly four original mounting holes. It passed an M3 bore
revision on 1 of 4 originally clean, unrelated boards and rejected 3 as
unsupported. The test-pad routing prototypes failed every zero-DRC search.

This milestone **uses native KiCad BOARD.GetBoardPolygonOutlines** to extract
true stitched Edge.Cuts polygon approximations, **including internal cutouts**.
It does not substitute bounding rectangles or invent hole coordinates.

| Frozen original source | Outline vertices | Cutouts | Source mounts | Strategy | Independent STEP |
| --- | ---: | ---: | ---: | --- | --- |
| dnlbauer/corax-keyboard | 85 | 1 | 0 | Non-clamping contour tray | PASS |
| rniwase/sdtv2csi | 40 | 0 | 0 | Non-clamping contour tray | PASS |
| justbuchanan/oasis | 39 | 1 | 1 | Non-clamping contour tray | PASS |
| protolux-electronics/trellis_core | 64 | 0 | 4 | Source-hole registration | PASS |

The adapter builds actual BRep **nominal unpopulated board**, source-outline
cartridge, identical reusable dock, and inspection gauge for each case.
KiCad polygon-derived edge contours, *not analytic arcs*, drive the extrusion.
The native-audit path separately re-loads KiCad original geometry, hole
coordinates and cutouts, and the CadQuery auditor re-imports STEP and
independently checks 3D boolean symmetric difference against the source.
All four STEP auditees passed with zero modeled nominal seating collision,
but no physical fit/tolerance is claimed.

### Real source revision propagation

The previously edited four-layer Protolux M3 candidate (HS #366) was also
processed as **one additional derivative, not an extra independent board**.
Hole diameters correctly propagate from 2.7 to 3.2 mm while outer contour
and four source XY coordinates remain fixed. The original revision's
**93 DRC warnings** become **97 after the M3 drill edit** (four additional
footprint-library mismatches). Fabrication HOLD continues.

**Contour study:** 4/4 original sources + 1/1 source derivative, two complete
fresh run directories with identical canonical results SHA-256:

`5669801c7b18a55cd41c371de23bbe08dd7979b2154b1ad235ce4030785bded9`

## First native electrical edit admitted on a distinct frozen source

`justbuchanan/oasis` (Apache-2.0 original, source SHA bound to frozen
`punkfab/pcb-corpus` commit) received an added **TP1 exposed F.Cu pad**
on original signal net `Net-(U2-IO9)`, reached by an actual **0.2 mm
front-copper branch trace** from the midpoint of an original same-net track.
Native KiCad 9 DRC: **0 error-level violations, 0 unconnected items**.

An auditor **separate from the generator** re-opened original and revised
native boards: **173 original pad identities, 263 original copper objects
and the full irregular outline/internal cutout preserved**; exactly one
new signal-branch copper object and one new exposed test pad; the branch
physically joins the original segment in the saved geometry. An actual
wrong-net injection of the new TP pad yielded **96 error-level findings and
one unconnected item**. That is a genuinely falsifying negative control,
not an expected fixture result written by a mock.

### Legacy KiCad UUID defect exposed and corrected

Corax original uses legacy `(tstamp UUID)` identities while KiCad 9
re-saves them as `(uuid "UUID")`. The initial tool identified thousands
of unchanged legacy IDs as *new*, changing excluded-item identities and
inducing 56 spurious solder-mask findings. The source-identity parser now
recognizes both formats and only stabilizes newly created objects. Another
repeatability defect from random UUID assignment order was resolved by
stable **serialization-order** UUID mapping and re-serializing the board
after normalization.

Two fresh runs of the Oasis electrical modification now produce the
**same exact editable PCB SHA-256**:

`7d79d7ad60ee3af376462d4640af8286c74b2bedad4f331d988e2f6e80211e58`

### Native edited PCB → actual probe guide STEP

The revised Oasis source also regenerates an **irregular-board contour
inspection carrier** and an additional **nominal, source-bound signal-probe
guide plate** with one 0.6 mm aperture centered precisely on TP1.
Independent source and STEP auditors re-opened the native board and STEP,
verified the 3D bore at both Z faces, confirmed the internal source cutout
and 0 BRep symmetric difference, and rejected 4 adversarial substitutions
(stale PCB SHA, shifted bore claim, lost source cutout, fake fabrication authority).

The theoretical radial margin of that 0.6 mm guide bore around a 1.0 mm pad
is **0.2 mm, without any allowance for manufacture, fit or alignment**.
This is therefore an *unpopulated-board design reference*, **not** a
validated pogo fixture, executable probe plan or safe installed overlay.

**Signal study:** two fresh full runs of exact source-bound
PCB edit → native DRC → independent source audit → contour CAD → 3D independent
audit → dedicated probe plate → independent CAD audit, each with identical
semantic result SHA-256:

`3351c23ff6eb79901ae7eddcf0a4992dac5b3d64bcb02de048c6e78a463a0c69`

## Important negative results

- Corax signal-track-tap pilot: **29 candidates, zero admitted**; under its
  source rules each surviving attempt retained a solder-mask bridge finding.
  We preserved the failure rather than counting a geometry-only change.
- The earlier #366 direct-pad routing searches failed 60 rniwase and 65
  Protolux candidates. Those negative controls remain part of the preceding
  milestone; this revision does not magically solve arbitrary autorouting.
- This milestone's 4/4 native contour adapters are on the **four previously
  selected original boards**. The success rate is not an unbiased estimate
  for the full 235-board corpus. Oasis was chosen for electrical development
  *after* inspecting the failed routing cases. **It is not a post-tuning,
  genuinely untouched electrical edit benchmark.**
- An error-free KiCad DRC proves none of circuit function, signal integrity,
  EMC, power management, populated-component clearance, material safety,
  contact force, human build efficiency, production yield or affordability.

## Reproduce with independent tooling

On Linux with native KiCad9 and `/usr/bin/python3` importing `pcbnew`,
plus a *separate* CadQuery Python environment:

```sh
git clone --filter=blob:none --no-checkout https://github.com/punkfab/pcb-corpus.git /tmp/hs-pcb-corpus
git -C /tmp/hs-pcb-corpus sparse-checkout set --no-cone README.md
git -C /tmp/hs-pcb-corpus checkout --detach 1e999b4eefd5fdfcc90dc376d2882390245a8e0d

/usr/bin/python3 projects/heldout-generality/run_contour_cohort.py \
  --corpus-repo /tmp/hs-pcb-corpus \
  --cad-python /path/to/cad-venv/bin/python \
  --out /tmp/hs-new-contour-evaluation

/usr/bin/python3 projects/heldout-generality/run_signal_access.py \
  --corpus-repo /tmp/hs-pcb-corpus \
  --cad-python /path/to/cad-venv/bin/python \
  --out /tmp/hs-new-signal-evaluation

/path/to/cad-venv/bin/python projects/heldout-generality/test_contour_signal.py
```

Every run refuses to overwrite prior evidence and reads pinned corpus Git
blobs with exact SHA-256 checks. The source-to-CAD and source-to-electrical
auditors are separate from generation. **Native KiCad source is not vendored
into HS**; a portable `hs-heldout-contour-and-signal-v3.zip` contains
attributed derived review models, a revised Oasis PCB, the exact source
licenses/attributions, native DRC and replay/audit receipts. That ZIP
can be rebuilt with `repack_contour_evidence.py` from retained evidence.

## Fabrication / operator HOLD

There was **no equipment purchased, board fabricated, signal measured,
motor driven, PCB probe contacted, print tested, calibration or physical
operation** in this milestone.

1. M3 Protolux footprint identity (M2.5 library) mismatch remains unresolved.
2. Edge nest tolerances, actual board thickness, connector position/height,
   top-side IC clearance, retention, screws, ESD/insulation and print warpage
   are unmeasured.
3. All nominal STEP board contours are tessellated Edge.Cuts outlines, not
   exact analytic arc/fab tolerances; within current source design units only.
4. New Oasis net signal integrity, test-point parasitics, manufacturing
   clearance in production, soldermask, access direction and under-load
   electrical safety require actual expertise and permitted testing.
5. No untouched new-device replication or second-machine physical repeat.

**Verdict:** RESEARCH-DIGITAL-PASS; FABRICATION-NOT-READY.

## Next meaningful gap

Pilot source-derived keepouts against actual top-side assembly/component BReps
and variable stackups; adopt native multi-layer/freeform contours, robust
source-zone repair, an actual KiCad router, and a new precommitted post-tuning
electrical edit cohort. Subsequently use one *permitted, low-voltage physical
test board* for a separately controlled and independently measured bench trial.
