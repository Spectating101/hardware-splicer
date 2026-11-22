# Device workspace: capability coverage (23 November 2026)

The owner asked whether the device workspace (`/devices/<scene id>`) shows everything HS can do. This map lists each capability, where it appears, the device it is demonstrated on, and what remains. A capability is listed as **shown** only when real records or real tool runs drive it.

## Shown in the device workspace

| Capability | How it appears | Demonstrated on | Source of truth |
|---|---|---|---|
| Assembled 3D device, any scene | The full-bleed model, parts searchable by name or reference | Fielddeck, Ender-3, HS-3G-B, both KiCad boards | the scene GLB and parts sidecar |
| Questions compose the view | Choosing a finding sets the revision, selection (several parts), explode and face view | all | the finding's `view` |
| Part fidelity | Each part's shape basis (custom, vendor STEP, envelope, unknown); stand-in results are marked | all | the sidecar, plus documented `geometry-basis.json` |
| Measured fit | Size, real collisions, stand-in overlaps, tight gaps grouped by value, touching parts | all five models | `scene_fit.py` via `/fit` |
| Display-in-opening measurement | Face view with the CAD lips, aperture and seam | Fielddeck | the stage's CAD section |
| Revision change | What changed from the earlier revision; Compare | Fielddeck 7 → 5 | the sidecar revision diff |
| Recorded blockers and connections | Open questions numbered the same as the pins on the model; each interface with its open checks | Fielddeck | the sidecar |
| Strategy before design | Each build/buy/salvage option with its known cost, uncosted gaps and risk; what was chosen for what, and why | Drone (X500 study, no model) | `engineering_decision.json` |
| KiCad DRC/ERC, live | Pass/fail per check class, every violation traced to the parts and nets it touches; a short lights both nets' copper | ESP32 board (92 errors), SPI board (clean) | `kicad-cli` via `/kicad` |
| Board copper | Each net's tracks, vias, pads and zone fills drawn on the board, named "Net X · copper" | both KiCad boards | `pcbnew` via `build_board_scene.py` |
| Next step per finding | Each open, failing or stand-in finding says what would resolve it | all | the finding's `next` |
| Design verification receipt | Checks, authority flags and non-claims | SPI board | `verification.json` |
| Simulation | Mission scenarios with their metrics; what the simulation leaves out | HS-3G-B | the study's `verification.json` |
| External GitHub tool | Commit-pinned, licence-checked tool run and its findings on the parts; discovered-but-not-run tools with the reason | SPI board (akcli; kdif not run) | the GitHub-signal verdict |
| Cost | Known total, unpriced lines and price basis | Fielddeck, SPI board | `BOM.csv` |
| Authority | "Physical fit not tested on hardware" always visible; no passed, ready or approved wording | all | tests enforce the state vocabulary |

## Not yet in the device workspace

| Capability | Where it lives today | What it would take |
|---|---|---|
| Revision history and invalidation chain | Project bench (Change history panel) | Link a scene to its HS project and show which evidence a revision invalidated |
| Engineering Change Dossier (Policy Lab → HS → Cite) | Bench Change history and `/change-dossier` | The same project link as the row above |
| Bench gates and physical authorization | Bench evidence pane | The same project link; physical gates stay owner-only |
| SPICE results on a circuit | Digital studies (drone, witness fixture) | A circuit-level scene with an evidence record of kind `spice` |
| Schematic 2D view joined to the 3D selection | KiCanvas in the design library | Embed KiCanvas next to the board model, sharing the selected reference (copper is now in 3D) |
| A canvas per kind of question (simulation plots, strategy comparison table) | Records only, in the questions list | Renderers chosen by finding kind; both reviewers asked for this |
| Owner decisions on a finding (accept, waive, needs bench test, ask the agent) | Bench review store | Write-back through the existing review store; never marks anything physically proven |
| A board inside its enclosure | None: no project pairs a board with a case | A project with both, so fit can be measured between board and case |
| Real component heights on boards | Assumed heights (`footprint-heights.json`) | The KiCad 3D model library, or datasheet heights per footprint |
| Asking the agent in plain words | Agent conversation API | A question box that asks the agent and composes the answer's view |

## Notable findings these views surfaced

- **The ESP32 servo board in `examples/` fails KiCad DRC badly:** 92 errors, including 14 shorts between nets. Six of the shorts are at the USB connector J1, including USB_D+ to USB_D-. It should not be treated as a working design.
- **The Fielddeck display rests on its rear trays.** Sampling alone read a 0.075 mm gap; exact measurement gives contact.
- **The drone strategy record is explicit that nothing is optimised yet.** "The lowest known partial price is not the cheapest complete drone; no custom or salvage cost is yet verifiable."

## Outside review (23 November 2026)

Two independent reviewers looked at eight screenshots: Gemini Neon (web, account b) and GPT-6 Luna (Codex). Both scored 6/10 for craft and 5-6/10 for usefulness. Their answers are in [`device-review-20261123/`](device-review-20261123/).

Changed because of the review, each checked in the browser:

- KiCad shorts showed only a component box. Board scenes now carry each net's copper, and a short highlights both nets.
- akcli listed info rows above its 21 warnings. Findings are now ordered most severe first.
- "Covers the glass edge" read as a fit verdict. It now reads "CAD estimate: … Physical fit not tested", and the stack-up caveat comes first.
- The seam question highlighted one pair of 16. Grouped findings now highlight every part in the group, up to 40.
- "Usually a designed seam" asserted intent. It now says "possibly a designed seam (intent not recorded)".
- Failing checks looked like neutral records. They have a red state word, and the header counts failing checks separately.
- The search hint was fixed to Fielddeck parts. It now comes from each device's own parts.
- What a question changed was invisible. The lens now states it: revision, number highlighted, face view, exploded.
- No finding said what to do. Each open or failing finding now has a "Next" line.
- Pins numbered only on the earlier revision had no row. Those blockers are now listed with their revision.

Not changed yet: a canvas per kind of question, decision write-back, a docked inspector and an animated transition. These are listed above.
