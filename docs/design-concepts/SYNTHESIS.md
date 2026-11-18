# Hardware Splicer interface: combined direction (draft for owner review, 2026-11-18)

Synthesised by Claude Opus 5.5 from four independent concepts in this directory (GPT-6.2 Sol, GPT-6.2 Astra, Gemini 4 Argon, an independent Claude Opus) and the three research files in `../design-research/`. Nothing here is built yet.

## The idea

**The project is a live casefile** (from the Opus concept). One document per project, in the order evidence flows: Goal → Requirements → Parts → Geometry and circuit → Studies and checks → Release assessment. Each section is a typed cell carrying the backend's authority label verbatim, its producer, age and the cells it depends on. Viewers (CadQuery 3D, KiCad board, PyBullet replay, toolpaths) live inside cells. When something upstream changes, the cells below visibly go stale and name their cause. The page moves when evidence moves.

Why this one: it is the only concept where a part substitution is something you *watch* cross the whole project, and it gives every capability one grammar. Teardown units, GitHub tools, sealed evaluations and repair cases are casefiles too, so learning one teaches all.

## What each concept contributes

| From | Taken |
|---|---|
| Opus | Casefile as the spine; dependency rail with one glyph per cell (settled, stale, unknown, blocker, changed, selected); header counts with "not assessed" distinct from zero; ripple marked only from the backend's impact result; suggestion cells with two-step agent approval; phone "needs a hand" filter. |
| Astra | **Pin, follow, return**: pin a moment (a sample in a run, a hole on a part), follow the part through teardown, inventory and wiring, then return to the pinned state with the new evidence in view. Adopted as the pinned-moment chip that travels with you. |
| Sol | Two clocks kept separate: run time only inside recorded studies, project time as an activity track you can step back through. "New activity" collects live agent updates until you choose Go live, so nothing yanks your view. Shareable deep links to revision + cell + selection + run time. Coverage line on every compare. |
| Argon | One-key **open beside**: while a cell is lifted, a second linked view (board beside sim, section beside harness) without a layout engine. Full-width BOM table with requirement, offer, owned stock unit and ranked alternates as separate records. Two-tier authorization: lightweight inbox for draft runs, frozen From/To change orders only for released parts. |
| Research | Rerun one time cursor across views; Interactive HTML BOM and tscircuit cross-probing; deltaKi coverage panel and blend; KiCad list-plus-marker findings; Onshape differences-only compare; marimo stale marking; Agent Inbox actions; InvenTree part vs stock unit. |

## Rejected (from the research gimmick list and the concepts' critiques)

Global force-directed graphs, live cursors for a small team, streamed agent "thoughts", user-composed tiling layouts, assumption sliders that make modelled numbers look measured, health scores, animation as state, chat as home, and any client-side summary of authority ("fit ok", "no upgrade").

## Build order

1. FieldDeck casefile in read mode from existing endpoints: header counts, rail, cells, Study cell from the existing DigitalStudyPanel.
2. The ripple on the real SC1635 7" → SC1975 5" display swap: draft, differences only, stale cells with causes, coverage, Run on draft.
3. Linked selection across BOM, CadQuery body and KiCad board, with "not linked" shown honestly.
4. Agent margin and suggestion cells with two-step approval and "base moved".
5. Lift, open beside and run-time follow on the HS-3G-B flight run, with pin and return.
6. Phone "needs a hand" view.
7. Workshop casefiles: tool factory (akcli, kdif, iBOM proposal), sealed evaluations, teardown units.

Acceptance: time to a justified decision on the FieldDeck swap and on the unavailable SO-ARM100 servo, entered both from Projects and from a direct BOM link. "Need the voltage evidence" counts as a correct outcome.
