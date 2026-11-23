# Bench art direction (2026-11-19)

This document has two parts. The first is the art-direction spec, written by Claude Opus 5.5 after it scored round E at 8.4 for craft and 8.9 for usefulness. The second is a set of binding amendments, which take precedence wherever they conflict with the spec. They come from GPT-6.2 Astra and Gemini 4 Argon, who reviewed the spec before any of it was built and both accepted the lower craft score. This document sits alongside FIELDDECK_SCENE_TARGET_20261119.md and supersedes it where they differ.


Baseline: round E. Units are mm, Z up.

## 1. Thesis

Parts sit on an inspection plate under one softbox: matte, grounded, and lit well enough that their form reads without edge lines. Every mark over them is a drafting mark that prints its source, and colour means only a change or a question.

Taken: Apple's large soft key and outline-free object; iyO's matte clay, reduced part set and hover float; Oryzo's thin dashed construction marks with end handles (not its depth of field); Teenage Engineering's single light pool on near-black; Rerun's neutral model under data-coloured overlays.

## 2. Rendering

**Tone mapping.** Neutral tone mapping, done as a `ToneMappingEffect` (mode NEUTRAL) in the composer, at exposure 1.05. Lines and pins use `toneMapped:false` so their hex values are exact.

**Environment.** `PMREMGenerator.fromScene(new RoomEnvironment(), 0.04)` (no network), `environmentIntensity` **0.32**, down from 0.55, which filled in the key and flattened the render.

**Light rig.** Positions are unit vectors × 2 × radius.

| Light | Direction | Elevation | Colour | Intensity | Shadow |
|---|---|---|---|---|---|
| Key | (−3, −5, 8), front-left | 55° | #FFF3E6 | 2.6 | yes |
| Fill | (6, −2, 2), right | 17° | #E6EEF7 | 0.45 | no |
| Rim | (2, 7, 4), back | 28° | #FFFFFF | 1.3 | no |

Acceptance: lit and shadowed faces of the top plate differ by at least 28 L*.

**Shadows.**
- **Contact shadow.** Two-scale: blur 1.4/512 at 0.45 plus 0.5/512 at 0.35 (feet). Re-render on explode settle, ≤ 30 Hz while dragging.
- **Key shadow map.** `PCFShadowMap`, radius 4, blurSamples 12, bias −0.0002, normalBias 0.02. Map 2048 high, 1024 standard: soft inter-layer shadows.
- **Floor.** Replace `GridHelper` with a shader grid: 10 mm lines at +3% luminance, 50 mm lines at +6%, fading radially to 0 at 0.6 × radius. Tag it "Grid 10 mm".

**Ambient occlusion.** n8ao 2.1.0 `N8AOPostPass` on postprocessing 6.39.x: aoRadius 3 mm, distanceFalloff 1.0, intensity 2.2, aoSamples 16, denoiseSamples 8, denoiseRadius 12, quality Medium. Ghosts, envelopes and all `LineSegments2` use `depthWrite:false`, so they never take AO.

**Anti-aliasing.** AO disables MSAA, so set `antialias:false` and use `SMAAEffect(HIGH)`. LineMaterial smooths its own lines.

**Frame budget.** Render on demand. iGPU at 1440×900, DPR 1.25: scene 6 ms, AO 3 ms, SMAA 1 ms.

| Tier | DPR | AO | AA | Shadow map |
|---|---|---|---|---|
| High | 2.0 | full resolution | SMAA | 2048 |
| Standard (iGPU default) | 1.25 | halfRes | SMAA | 1024 |
| Reduced | 1.0 | off | MSAA 4× | off; contact shadow baked once per explode |

p90 over the first 60 interactive frames > 14 ms drops one tier. Orbiting uses halfRes AO and no contact re-render; one full frame on `rest`.

## 3. Materials

`MeshStandardMaterial`, metalness 0, no textures or noise: detail comes only from geometry, AO and creases, never an implied finish.

| Source | Colour | Roughness | Treatment |
|---|---|---|---|
| Custom CAD | #D9CFBE | .80 | Ink creases |
| Vendor | #9C9EA0 (neutral grey; was #93A3AE, see amendment 2026-11-19) | .86 | Ink creases. Never glass, IOR, clearcoat or emissive |
| Measured (new) | #E4E2DC | .74 | Creases at 100%. Only if the sidecar holds a measurement record (instrument, date) |
| Donor, as received (new) | #858B91 | .90 | 135° hatch, 12 px, 6% contrast |
| Envelope | 6% unlit fill, #A5AEB5 | n/a | Dashed 6/4 px; no AO or shadow |
| Proxy | #A6A098 | .88 | 45° hatch, 8 px, 10% contrast |
| Unknown | none | n/a | Dotted 1/3 px outline, #9097A0; "?" at the bounds centre |

A donor known only as an envelope (plotter `REFERENCE_ENVELOPE_*`) keeps the envelope treatment, donor-tinted.

**Dimmed unchanged (Compare).** Lit as normal; colour lerped 80% to its luminance grey, value × 0.62: custom #8E8B85, vendor #737A80 (not brown #6E685F). Edges 25%; shadows kept.

## 4. Line language

**Extraction.** Creases: `EdgesGeometry` 32° (custom, measured), 42° (vendor, suppresses faceting), drawn as ink #1A1D22 at 35%, 1 px. Silhouettes (high tier): depth Sobel, 0.5 mm threshold, 1 px #0B0D10 at 60%, closing standoffs and feet.

**Diff colour.** Apply it only to outlines (silhouette plus creases over 60°), never to every crease. This removes the amber lattice.

| Role | Colour | Width | Dash |
|---|---|---|---|
| Added | #2DD4BF | 1.5 px | solid |
| Changed | **#A78BFA** violet | 1.5 px | solid |
| Removed | #F17E70 | 1.25 px | 6/4 px |
| Old revision of a changed part | #F17E70 at 70% | 1.25 px | 6/4 px |
| Questions | #F59E0B, pins only | n/a | n/a |
| Selection | #F2EFE7 brackets, 10 px arms, 1.5 px, 8 px pad | n/a | n/a |

Selected edges 100%, others 50%.

**Changed parts state the change:** a label sub-line such as "Bounds −12.40 X · 2 holes moved · computed", from bounds, volume and hole-count differences.

**Ghosts without stipple.**
1. Weld endpoints at 0.01 mm and chain them into polylines.
2. Simplify with Douglas–Peucker at 0.2 mm.
3. Cull old chains that lie within 0.15 mm of a current edge.
4. Draw chains under 3 mm, and circles under 6 mm, solid at 40%.
5. Run the dash phase continuously along each chain, with `dashScale` taken from that chain's own depth.

## 5. Drafting and dimensions (ISO 128 / 129-1)

SVG overlay. Extension lines 0.75 px, 3 px gap from the object, 4 px past the dimension line. Dimension lines 1 px. Filled 30° arrows, 7 px; chained dimensions use 6 px 45° ticks. Text above and parallel, 3 px gap, line unbroken; vertical text reads bottom-to-top; Plex Mono 11 px, U+2212 minus. Centre marks: 12 px cross with chain lines.

| Source | Line | Value | Tag |
|---|---|---|---|
| Computed | solid #E6E8EB | `143.40` | "computed", 10 px #9097A0 |
| Datasheet | dashed 4/3, #9097A0 | `(103.7)`: ISO auxiliary dimension, digits verbatim | "datasheet [n]", linked to the citation |
| Measured | solid | `143.38` | "measured · caliper · date" |
| Unknown | dotted 1/3 | `?` | the amber question pin if one is linked, otherwise "unknown" |

## 6. Face view: the fit question

Face view uses an orthographic camera square to the display normal, with explode at 0. The question is whether the 5-inch glass clears the faceplate aperture, and whether the standoffs align with the display's mounting holes.

It draws:
1. Aperture loop: mid-thickness section of the Face parts, 1.5 px #D9CFBE.
2. Glass outline projected to that plane, 1.5 px #93A3AE; active area dashed, datasheet.
3. Standoff centre marks at mesh centroids, computed.
4. Datasheet hole pitch `(103.7 × 51)` in the strip only, unless the datasheet gives its offset from the glass edge.
5. 7-inch outline: off by default, 35% when toggled.

**When clearances can be derived** (the loop is closed and the glass is within 0.5° of the section plane): draw four signed chained dimensions, left, right, top and bottom. A negative gap gets an amber 45° hatch, "CAD overlap 1.20 · computed", linked to a question. The strip reads, for example, "Min clearance 1.85 mm, left · computed from CAD · physical fit unknown".

**When they cannot:** a `?` dimension per side and the reason, e.g. "Clearance not derivable: no closed aperture loop in Face Rear Left". Never datasheet arithmetic.

## 7. Motion

| Moment | Duration | Easing | Behaviour |
|---|---|---|---|
| Intro | 1100 ms | below | 0–250 plate fades in (linear). 150–750 explode 0→0.6, staggered 40 ms per Z group (6 groups max), `cubic-bezier(.33,1,.68,1)`. 600–850 removed outline draws on by dash offset. 800–1100 labels fade in and rise 2 px. Camera stays fixed. Any input skips to the end |
| Fly-to | 450 ms | `(.65,0,.35,1)` | Moves the target. Distance changes only if the part is under 15% of viewport height or off-screen. Azimuth turns at most 30° |
| Face view | 650 ms | `(.65,0,.35,1)` | Explode goes to 0 over 400 ms, FOV dolly-zooms from 26° to 4°, then a silent swap to orthographic. Drafting fades in over 150 ms |
| Explode button | 500 ms | easeOutCubic | Slider input is direct, with no easing |
| Hover | 120 ms | linear | Opacity changes, plus a 2 mm presentation float along the explode vector |

**Never animated:** numbers, state colours, pins (no pulse), shadows; labels lock to projection with no lag.

**Reduced motion:** camera and explode snap, intro shows its end frame, only opacity fades ≤ 150 ms remain.

## 8. Typography

Keep IBM Plex Sans and Mono: the app's system, tabular Mono figures stack dimensions, true minus sign.

- **Scale:** 11/12/14/20/32 px; weights 400/500/600.
- **Display numbers (at most two):**
  - Face view: the minimum clearance, or "Clearance unknown", in Sans 500 at 32 px.
  - Compare: the footprint delta "−45.92 × −28.78 mm" in Mono 500 at 20 px.
- **Header:** "Physical fit · unknown" at 14 px, weight 600.
- **Labels:** scene labels in 11 px Mono, panel text at 12 px.

## 9. Generic bench states

**Project picker** (facts only, no readiness):
```
 Projects
 [thumb] Fielddeck display swap  2 revisions  13 open
 [thumb] Pen plotter (Ender-3)   1 revision    4 open
 [  ?  ] HS-3G-B drone           no geometry   9 open
```

**Single revision (pen plotter).** No Compare and no Change legend:
```
 <- Pen plotter  rev A              Physical fit · unknown
 By source  :  [matte stage]               :  E plate
 Custom 3   :  pen adapter, clamp          :  Donor, as rcvd
 Donor 1    :  E plate (mfr STEP)          :  (12.0)
 Env. 18    :  18 dashed envelopes         :  datasheet [2]
            :  [Front] [Top] [Side] [Iso]  :
```

**No geometry (drone).** No stage and no guessed placeholder box:
```
 <- HS-3G-B drone                 Geometry unavailable
 frame ?   :  Frame geometry unavailable   :  frame_cut
 stack ?   :  STEP not imported            :  sha256 3f9a..
 motors ?  :  [Import STEP]                :  Bounds unknown
           :  Records, questions usable    :  Questions 1,4,7
```

## 10. Tasks, ranked by impact on the score (one engineer-day each)

1. **Light rig** per §2, two-scale contact shadow, faded grid; check L*.
2. **Composer:** N8AO, SMAA, tone mapping, `depthWrite:false` overlays, tiers.
3. **Line language:** ink creases, outline-only diff, violet changed; amber-only-on-pins test.
4. **Ghost cleanup:** weld, chain, simplify, cull, per-chain dash.
5. **Face view fit drawing** with signed clearances and the not-derivable state.
6. **Dimension component** with four source variants; every-value-has-a-source test.
7. **Changed-part delta summary** in label and Inspector.
8. **Materials:** dimmed, measured (gated), donor; legend.
9. **Motion:** intro, fly-to, Face view, reduced motion.
10. **Generic states:** picker, single-revision, no-geometry.

## Binding amendments (pre-build review, Astra + Argon)

**Tokens**
- Changed is violet #A78BFA, used on outlines and edges sharper than 60° only.
- Amber #F59E0B is for question pins only.
- Internal creases are ink #1A1D22 at 35%.

**Render pipeline**
- Pass order:
  1. Scene.
  2. N8AO post pass.
  3. Technical overlay pass (lines, ghosts, envelopes). It shares scene depth, so lines never receive AO halos.
  4. ToneMappingEffect(NEUTRAL).
  5. SMAA.
- Set `renderer.toneMapping = NoToneMapping` when the composer tone-maps, to avoid tone-mapping twice.
- Use PCFShadowMap with `radius`. Do not use `blurSamples`, which only works with VSM.
- The contact shadow is baked at rest. While dragging, cross-fade instead of re-rendering it every frame.
- Depth-Sobel silhouettes are High tier only.
- Treat 60 fps as unverified. Measure orbit and explode-drag at 1440×900 and DPR 1.25 on an integrated GPU, and drop AO before annotation legibility.
- Judge the lighting by whether the display, the aperture lip and the feet stay distinguishable with edges hidden, not by an L* number alone.

**Materials**
- **Measured:** applies only to the feature that has a measurement record.
- **Donor:**
  - A donor shown from manufacturer STEP keeps vendor treatment and is labelled "Donor CAD (unverified)".
  - "As received" requires an inspection record of the actual unit.
- **Hatches:** procedural in screen space (`onBeforeCompile`, `gl_FragCoord`). Never UV textures.

**Lines and ghosts**
- Weld ghost edges into polylines, simplify them, and cull them by proximity at 0.15 mm, but keep real sub-0.15 mm changes.
- Dashes are in screen space with no depth scaling.
- Change summaries state only deterministic mesh deltas (bounds, volume). Never "holes moved" without declared hole axes.

**Dimensions**
- Datasheet values carry their citation. No parentheses, because ISO uses parentheses for auxiliary dimensions.
- Dimensions are computed from assembled coordinates even while the view is exploded.
- Keep source precision, and name the revision and the feature.

**Face view**
- Both footprints stay visible: the 7-inch outline at 35% in Compare, off in 5-inch mode.
- Aperture inspection is a separate layer:
  - Section the combined face sub-assembly (Face Rear Left + Right), welding seam vertices at 0.05 mm before checking that the loop closes.
  - Label the result "Projected CAD gap · section <name>".
  - Mark spacers "Spacer mesh centroid · computed (hole axis unverified)".
  - Any gap that cannot be derived shows "?" with its reason.

**Motion**
- No hover lift. Show hover by edge opacity only.
- Scale camera near and far with distance during the Face view zoom.
- Restore the exact camera and explode setting on return.

**Type**
- No 32 px clearance number. "Physical fit · Unknown" stays primary.
- Numbers are 20 px mono and qualified, for example "Min projected XY gap · 1.85 mm · computed".

**Added scope (both reviewers)**
- A composed camera for each inspection, plus Isolate (Onshape convention).
- Pins behind geometry dim to 35% and get a tick down to their anchor.
- Tapping a crowded pin on phone opens its question in the sheet.
- A section plane through the display and spacer centreline, for Z stack-up.
- A two-point measure that reports dX, dY, dZ and distance, tagged with the weaker source of the two points.

**Dated amendments**
- 2026-11-19 vendor neutral #9C9EA0: reviewers read #93A3AE beside teal as cyan.
