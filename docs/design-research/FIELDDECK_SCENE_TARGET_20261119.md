# Fielddeck scene: consolidated 10/10 target (2026-11-19)

Merged from three independent "what is your 10/10" answers: GPT-6.2 Astra (Codex, saw the screenshots), Gemini 4 Argon (agy, saw the screenshots) and Claude Opus 5.5. These came after their visual reviews scored the current build 6–6.5 for craft and 7–7.5 for usefulness. Captures are in `review-ui/fielddeck-scene-20261119/`.

## Concept
A revision bench for one question: does the 5-inch display fit, and what is still unknown? Every mark in the scene is either a CAD number or an open question pinned to a place. The feel is a part on an inspection plate under good light. There are no theatrics.

## Agreed by all three
- The canvas is full-bleed on this route, and the app nav does not frame it. Panels float over the canvas.
- Geometry basis is shown by the surface treatment and the diff state by a single edge colour. They are two separate axes, so the legend has two groups.
- Labels never truncate a qualifier. Scene labels sit in clear space at the end of an elbow leader, and full text lives in the Inspector.
- Cables get A/B endpoint marks and a "Routing unknown" note. No drawn route (Gemini proposed a straight vector plus a frustum; rejected).
- Vendor models stay matte. No glass, IOR or clearcoat (Gemini's own refusal list agrees).
- No bloom, no pulsing, no green, no readiness score and no progress count.
- Inspector order: the engineering question first ("Physical fit · Unknown"), each unknown shown once, sidecar state words verbatim, raw keys secondary.
- Phone: the stage gets about 55–60% of the height, a bottom sheet with a peek, the mode switch in a single strip, and 44 px targets.

## Decisions where they differed
| Topic | Pick | Why |
|---|---|---|
| Left side | Floating 240 px tree grouped by diff state: Added, Changed, Removed, Interfaces, then Unchanged collapsed (Gemini) | Onshape's "differences only" convention; the app nav shrinks to a 40 px top bar on this route |
| Unchanged parts in Compare | Same material, 40% luminance and desaturated | Gemini's dark slate re-encoded the diff into fill colour. Dimming keeps basis and diff separate while letting the diff pop |
| Blockers | Numbered pins at the part or interface centre. The header, tree and Inspector share the numbers (Claude, plus Gemini's reticle form) | `parts.json` blockers carry `part_id`, so every pin has a real location |
| Intro | ~1.1 s: plate grid, then the lift to the default explode, then the removed 7-inch outline, then the labels. Ends at a three-quarter view. Any input skips it; reduced motion skips straight to the end | Astra and Gemini agree; Claude's top-down ending moves to Face view |
| Face view | A button that squares the camera to the display, with the 7-inch dashed and 5-inch solid perimeters in the same frame and CAD deltas in mm (Astra + Claude) | The "wow" moment, one click away instead of forced |
| Changed parts | Compare draws the old revision's edges dashed crimson on the changed part (Gemini's ghost-delta) | The models share a coordinate frame, so this is real geometry, not inference |
| Elevation ruler | Optional; shows CAD Z only at explode 0, otherwise labelled "presentation offset" | Gemini's live-tracking ruler would print fake elevations while exploded |
| Plumb lines through mounting holes | Deferred | Hole axes are not in the sidecar yet; drawing them needs extraction first |
| Type | Keep the app's IBM Plex Sans and Plex Mono, tabular numerals | It is already the app's system; Astra and Gemini picked different pairs |
| Case | Sentence case, mono state words. No uppercase bracket badges | Gemini's `[BASIS: VENDOR_STEP]` is shouty and slows reading |

## Tokens
- **Surfaces.** Canvas #0E1116, floor gradient to #161B22, panels rgba(14,17,22,0.90) with blur 12 px and a 1 px #22262E border.
- **Text.** #E6E8EB, secondary #9097A0.
- **Basis materials** (metalness 0):

  | Basis | Treatment |
  |---|---|
  | Custom CAD | #D8CCB6, roughness .84 |
  | Vendor STEP | #94A6B2, roughness .78 |
  | Envelope | dashed edges, 6% fill, 45° hatch |
  | Proxy | #A6A098, 8 px hatch |
  | Unknown | dotted outline, "?" |

- **Diff edges** (1.5 px): added #2DD4BF, changed #E0A040, removed #F17E70 dashed 5/3.
- **Selection.** Neutral #F2EFE7 corner brackets.
- **Amber #F59E0B** is used only for blockers and open questions.
- **Spacing.** 4/8/12/16/24/32.
- **Panel radius.** 4 px.
