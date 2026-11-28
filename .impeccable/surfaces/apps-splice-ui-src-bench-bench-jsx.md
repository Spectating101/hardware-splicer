---
version: 1
slug: "apps-splice-ui-src-bench-bench-jsx"
primary_target: "apps/splice-ui/src/bench/Bench.jsx"
related_targets: ["apps/splice-ui/src/bench/bench.css"]
---

## Surface

Workbench (`/`, `apps/splice-ui/src/bench/`). Mode: Operate. The owner at a large desk screen follows and runs HS's tools; phone is for status only.

## Audience, job, constraints

- Owner first, agents drive. Job: see the spine (HS's 14-step board pipeline) with a recorded run over it, open any of the 39 HS tools or 21 outside tools, run a tool from its schema, read the engine's result verbatim.
- Every label and outcome comes from the backend (`/v1/bench/*`, `/v1/toolbelt/*`). No "ready" badges. Not run and not recorded are first-class states.

## Direction contract

THESIS: HS opens into the tool itself, as Unity or Premiere do: a docked editor with the pipeline in the middle. It refuses the marketing front door and the card-grid dashboard.
OWN-WORLD: near-black ground (#0f1114) with rounded panel islands (#181b1f); hairline rules; one HS green accent (#3ebd86) for selection, gates and Run; outcome marks (filled/hollow/dashed); IBM Plex Sans for the interface and Plex Mono only for ids, paths and numbers.
STORY: the visitor sees what the pipeline did on a real board, which outside tool sits at each step and what it measured, then runs a tool and reads its result and its limits.
FIRST VIEWPORT: top bar with the jump box (Ctrl K). Explorer left (spine steps, HS tools by job, outside tools by role). Centre tabs Spine/Board/Measured/Result with the 14 steps as stations on two lines and gates marked. Inspector right with the selected step, tool or outside tool and the Run button bottom-right. Console below the centre.
FORM: canon (docked pro editor), the standing exit, chosen by the owner over the dealt parts-cabinet, datasheet and transit-map directions; seed:7fe5ea19a54230c1
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
